import gradio as gr
import serpapi
import json
import math
import os
import re
from dotenv import load_dotenv

# 1. 기본 설정
load_dotenv()
API_KEY = os.getenv("SERPAPI_API_KEY")

# --- 상수 정의 ---
AREA_OPTIONS = [
    "서울", "인천", "대전", "대구", "광주", "부산", "울산", "세종",
    "경기도", "강원도", "충청북도", "충청남도", "경상북도", "경상남도",
    "전라북도", "전라남도", "제주도"
]
CATEGORY_OPTIONS = {
    "전체": "가볼만한 곳", "관광지": "관광지", "문화시설": "문화시설", "행사/공연/축제": "축제",
    "여행코스": "여행코스", "레포츠": "레포츠", "숙박": "숙소", "쇼핑": "쇼핑", "음식점": "맛집"
}
ROWS_PER_PAGE = 10
PAGE_WINDOW_SIZE = 5

# --- 위치 정보를 가져오는 JavaScript ---
get_location_js = """
async () => {
    const getPosition = () => new Promise((resolve, reject) => navigator.geolocation.getCurrentPosition(resolve, reject));
    try {
        const pos = await getPosition();
        return [pos.coords.latitude, pos.coords.longitude];
    } catch (error) { return ["오류", "위치를 가져올 수 없습니다."]; }
}
"""

# --- SerpAPI 호출 함수 ---
def search_serpapi(params):
    if not API_KEY:
        raise gr.Error("SerpAPI 키가 설정되지 않았습니다. .env 파일에 SERPAPI_API_KEY를 추가해주세요.")
    
    base_params = {"api_key": API_KEY, "gl": "kr", "hl": "ko"}
    all_params = {**base_params, **params}
    
    try:
        client = serpapi.Client()
        results = client.search(all_params)
        return results.as_dict()
    except Exception as e:
        print(f"[SerpAPI Error] {e}")
        raise gr.Error(f"API 호출에 실패했습니다: {e}")

# --- 기능별 함수 ---
def find_nearby_places_serp(latitude, longitude):
    if not latitude or not longitude:
        return gr.update(choices=[], value=None), {}
    
    params = {
        "engine": "google",
        "q": f"주변 관광지",
        "ll": f"@{latitude},{longitude},15z" # 위치정보 추가
    }
    try:
        search_results = search_serpapi(params)
        
        # local_results 우선 사용, 없으면 organic_results 사용
        places = []
        if "local_results" in search_results and "places" in search_results["local_results"]:
            places = search_results["local_results"]["places"]
        elif "organic_results" in search_results:
            places = search_results["organic_results"]

        if not places:
            return gr.update(choices=[], value=None), {}
            
        # places_info에는 제목만 저장. 상세 정보는 제목으로 재검색.
        places_info = {item['title']: item for item in places if 'title' in item}
        return gr.update(choices=list(places_info.keys()), value=None), places_info
        
    except Exception as e:
        print(f"[find_nearby_places_serp error] {e}")
        gr.Warning(f"오류가 발생했습니다: {e}")
        return gr.update(choices=[], value=None), {}

def update_page_view_serp(area_name, category_name, page_to_go):
    try:
        page_to_go = int(page_to_go)
        if page_to_go < 1: page_to_go = 1
        
        query = f"{area_name} {CATEGORY_OPTIONS.get(category_name, '가볼만한 곳')}"
        start_index = (page_to_go - 1) * ROWS_PER_PAGE
        
        params = {
            "engine": "google",
            "q": query,
            "start": start_index,
            "num": ROWS_PER_PAGE
        }
        
        search_results = search_serpapi(params)
        
        # local_results 우선 사용, 없으면 organic_results 사용
        places = []
        if "local_results" in search_results and "places" in search_results["local_results"]:
            places = search_results["local_results"]["places"]
        elif "organic_results" in search_results:
            places = search_results["organic_results"]

        places_info = {item['title']: item for item in places if 'title' in item}
        
        search_info = search_results.get("search_information", {})
        total_count = search_info.get("total_results", 0)
        total_pages = math.ceil(total_count / ROWS_PER_PAGE)

        # 페이지네이션 UI 로직 (app.py와 동일)
        half_window = PAGE_WINDOW_SIZE // 2
        start_page = max(1, page_to_go - half_window)
        end_page = min(total_pages, start_page + PAGE_WINDOW_SIZE - 1)
        if end_page - start_page + 1 < PAGE_WINDOW_SIZE:
            start_page = max(1, end_page - PAGE_WINDOW_SIZE + 1)
        page_numbers_to_show = list(range(start_page, end_page + 1)) if total_pages > 1 else []

        return (
            area_name, category_name, page_to_go, total_pages, places_info,
            gr.update(choices=list(places_info.keys()), value=None),
            gr.update(choices=page_numbers_to_show, value=page_to_go),
            gr.update(interactive=page_to_go > 1),
            gr.update(interactive=page_to_go > 1),
            gr.update(interactive=page_to_go < total_pages),
            gr.update(interactive=page_to_go < total_pages),
            gr.update(visible=total_pages > 1)
        )
    except Exception as e:
        print(f"[update_page_view_serp error] {e}")
        gr.Warning(f"오류가 발생했습니다: {e}")
        return area_name, category_name, 1, 1, {}, gr.update(choices=[], value=None), gr.update(choices=[], value=None), gr.update(interactive=False), gr.update(interactive=False), gr.update(interactive=False), gr.update(interactive=False), gr.update(visible=False)

def get_details_serp(selected_title, places_info):
    if not selected_title or not places_info:
        return "", ""

    try:
        # 선택된 제목으로 상세 정보를 재검색
        detail_results = search_serpapi({"engine": "google", "q": selected_title})
        
        # JSON 결과를 예쁘게 포맷팅한 문자열로 변환
        pretty_json = json.dumps(detail_results, indent=2, ensure_ascii=False)
        
        # 사용자의 요청에 따라, 가공하지 않은 JSON 원본을 두 출력란에 모두 표시
        return pretty_json, pretty_json
        
    except Exception as e:
        print(f"[get_details_serp error] {e}")
        return f"상세 정보 처리 중 오류: {e}", "정보를 가져오는 데 실패했습니다."

# --- Gradio 인터페이스 구성 (app.py와 거의 동일) ---
with gr.Blocks(title="SerpAPI 관광 정보 앱") as demo:
    gr.Markdown("## SerpAPI Google Search를 활용한 관광 정보 조회")
    with gr.Tabs():
        with gr.TabItem("내 위치로 검색"):
            places_info_state_nearby = gr.State({})
            with gr.Row():
                get_loc_button = gr.Button("내 위치 가져오기")
                lat_box, lon_box = gr.Textbox(label="위도", interactive=False), gr.Textbox(label="경도", interactive=False)
            search_button_nearby = gr.Button("이 좌표로 주변 관광지 검색", variant="primary")
            radio_list_nearby = gr.Radio(label="관광지 목록", interactive=True)
            with gr.Accordion("상세 정보 보기", open=False):
                raw_json_n = gr.Textbox(label="Raw JSON", lines=10)
                formatted_n = gr.Markdown(label="Formatted")
            
            get_loc_button.click(fn=None, js=get_location_js, outputs=[lat_box, lon_box])
            search_button_nearby.click(fn=find_nearby_places_serp, inputs=[lat_box, lon_box], outputs=[radio_list_nearby, places_info_state_nearby])
            radio_list_nearby.change(fn=get_details_serp, inputs=[radio_list_nearby, places_info_state_nearby], outputs=[raw_json_n, formatted_n])

        with gr.TabItem("지역/카테고리별 검색"):
            current_area = gr.State("서울")
            current_category = gr.State("전체")
            current_page = gr.State(1)
            total_pages = gr.State(1)
            places_info_state_area = gr.State({})

            with gr.Row():
                area_dropdown = gr.Dropdown(label="지역", choices=AREA_OPTIONS, value="서울")
                category_dropdown = gr.Dropdown(label="카테고리", choices=list(CATEGORY_OPTIONS.keys()), value="전체")
            search_by_area_btn = gr.Button("검색하기", variant="primary")
            
            radio_list_area = gr.Radio(label="관광지 목록", interactive=True)
            
            with gr.Row(visible=False) as pagination_row:
                first_page_btn = gr.Button("<< 맨 처음")
                prev_page_btn = gr.Button("< 이전")
                page_numbers_radio = gr.Radio(label="페이지", interactive=True, scale=3)
                next_page_btn = gr.Button("다음 >")
                last_page_btn = gr.Button("맨 끝 >>")

            with gr.Accordion("상세 정보 보기", open=False):
                raw_json_a = gr.Textbox(label="Raw JSON", lines=10)
                formatted_a = gr.Markdown(label="Formatted")
            
            outputs_for_page_change = [current_area, current_category, current_page, total_pages, places_info_state_area, radio_list_area, page_numbers_radio, first_page_btn, prev_page_btn, next_page_btn, last_page_btn, pagination_row]
            page_inputs = [current_area, current_category]

            def create_page_change_fn(page_no_fn):
                def page_change_fn(area, cat, current_page_no):
                    return update_page_view_serp(area, cat, page_no_fn(current_page_no))
                return page_change_fn

            search_by_area_btn.click(update_page_view_serp, inputs=[area_dropdown, category_dropdown, gr.State(1)], outputs=outputs_for_page_change)
            search_by_area_btn.click(lambda area, cat: (area, cat), inputs=[area_dropdown, category_dropdown], outputs=[current_area, current_category])

            first_page_btn.click(create_page_change_fn(lambda p: 1), inputs=page_inputs + [current_page], outputs=outputs_for_page_change)
            prev_page_btn.click(create_page_change_fn(lambda p: p - 1), inputs=page_inputs + [current_page], outputs=outputs_for_page_change)
            next_page_btn.click(create_page_change_fn(lambda p: p + 1), inputs=page_inputs + [current_page], outputs=outputs_for_page_change)
            last_page_btn.click(lambda area, cat, pages: update_page_view_serp(area, cat, pages), inputs=page_inputs + [total_pages], outputs=outputs_for_page_change)
            page_numbers_radio.select(lambda area, cat, page: update_page_view_serp(area, cat, page), inputs=page_inputs + [page_numbers_radio], outputs=outputs_for_page_change)

            radio_list_area.change(fn=get_details_serp, inputs=[radio_list_area, places_info_state_area], outputs=[raw_json_a, formatted_a])

if __name__ == "__main__":
    try:
        import serpapi
        from dotenv import load_dotenv
    except ImportError:
        print("필수 라이브러리가 설치되지 않았습니다.\npip install google-search-results python-dotenv")
        exit()
    
    load_dotenv()
    if not os.getenv("SERPAPI_API_KEY"):
        print("SerpAPI 키가 설정되지 않았습니다. .env 파일에 SERPAPI_API_KEY를 추가해주세요.")
        exit()
        
    demo.launch(debug=True)