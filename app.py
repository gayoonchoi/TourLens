import gradio as gr
import requests
import requests.adapters
import urllib3
import json
import re
import math
from urllib.parse import quote
import os
from dotenv import load_dotenv
import csv
import io
import tempfile

# 1. 기본 설정
load_dotenv()

class CustomAdapter(requests.adapters.HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        context = urllib3.util.ssl_.create_urllib3_context(ciphers='DEFAULT@SECLEVEL=1')
        kwargs['ssl_context'] = context
        return super(CustomAdapter, self).init_poolmanager(*args, **kwargs)

TOUR_API_KEY = os.getenv("TOUR_API_KTY")
API_KEY = quote(TOUR_API_KEY) if TOUR_API_KEY else ""
BASE_URL = "https://apis.data.go.kr/B551011/KorService2/"
session = requests.Session()
session.mount("https://", CustomAdapter())

common_params = {
    "_type": "json",
    "MobileOS": "ETC",
    "MobileApp": "AppTest",
    "serviceKey": API_KEY
}

# --- 선택용 데이터 목록 ---
AREA_CODES = {
    "서울": 1, "인천": 2, "대전": 3, "대구": 4, "광주": 5, "부산": 6, "울산": 7, "세종": 8,
    "경기도": 31, "강원도": 32, "충청북도": 33, "충청남도": 34, "경상북도": 35, "경상남도": 36,
    "전라북도": 37, "전라남도": 38, "제주도": 39
}
CONTENT_TYPE_CODES = {
    "전체": None, "관광지": "12", "문화시설": "14", "행사/공연/축제": "15",
    "여행코스": "25", "레포츠": "28", "숙박": "32", "쇼핑": "38", "음식점": "39"
}
ROWS_PER_PAGE = 10
PAGE_WINDOW_SIZE = 5

# --- CSV 및 상세 정보 표시에서 제외할 키 목록 ---
EXCLUDED_KEYS = {
    'createdtime', 'modifiedtime', 'cpyrhtDivCd', 'areacode', 'sigungucode',
    'lDongRegnCd', 'lDongSignguCd', 'lclsSystm1', 'lclsSystm2', 'lclsSystm3',
    'zipcode', 'mapx', 'mapy', 'mlevel',
    'agelimit', 'bookingplace', 'placeinfo', 'subevent', 'program',
    'discountinfofestival', 'spendtimefestival', 'festivalgrade',
    'progresstype', 'festivaltype', 'serialnum', 'infoname', 'fldgubun'
}

def is_key_excluded(key):
    """키가 제외 대상인지 확인합니다."""
    if key == 'eventenddate':
        return False
    if not key: return True
    return 'id' in key.lower() or key.lower().startswith('cat') or key in EXCLUDED_KEYS

def format_json_to_clean_string(json_data):
    """JSON 데이터를 필터링하고 사람이 읽기 쉬운 마크다운 문자열로 변환합니다."""
    if not isinstance(json_data, dict):
        return str(json_data)

    items = json_data.get('response', {}).get('body', {}).get('items', {}).get('item', [])
    if not items:
        return "표시할 정보가 없습니다."
    
    if isinstance(items, dict):
        items = [items]

    output_lines = []
    for item in items:
        # 이미지 URL들을 먼저 처리하여 맨 위에 표시
        image_keys = ['firstimage', 'firstimage2']
        for key in image_keys:
            value = item.get(key)
            if value and 'http' in str(value):
                output_lines.append(f"![{key}]({value})")
        
        # 나머지 텍스트 정보 처리
        for key, value in item.items():
            if key in image_keys: continue # 이미 처리했으므로 건너뜀

            if not is_key_excluded(key) and value and str(value).strip():
                if key == 'homepage':
                    match = re.search(r'href=["\\](["\\][^"\\]+)["\\]', str(value))
                    value = match.group(1) if match else clean_html(str(value))
                
                cleaned_value = clean_html(str(value))
                
                if cleaned_value:
                    output_lines.append(f"**{key}**: {cleaned_value}")
        output_lines.append("---")
    
    if output_lines:
        output_lines.pop()

    return "\n\n".join(output_lines) if output_lines else "표시할 정보가 없습니다."


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

def clean_html(raw_html):
    if not raw_html:
        return ""
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html)
    return cleantext.strip()

# --- API 호출 및 데이터 처리 함수들 ---
def find_nearby_places(latitude, longitude):
    if not latitude or not longitude: return gr.update(choices=[], value=None), {}
    try:
        params = {**common_params, "mapX": str(longitude), "mapY": str(latitude), "radius": "5000", "numOfRows": "20"}
        response = session.get(f"{BASE_URL}locationBasedList2", params=params)
        response.raise_for_status()
        data = response.json()
        items = data.get('response', {}).get('body', {}).get('items', {}).get('item', [])
        if isinstance(items, dict): items = [items]
        if not items: return gr.update(choices=[], value=None), {}
        places_info = {item['title']: (item['contentid'], item['contenttypeid']) for item in items if 'title' in item}
        return gr.update(choices=list(places_info.keys()), value=None), places_info
    except Exception as e:
        print(f"[find_nearby_places error] {e}")
        return gr.update(choices=[], value=None), {}

def update_sigungu_dropdown(area_name):
    if not area_name: return gr.update(choices=[], interactive=False)
    try:
        area_code = AREA_CODES.get(area_name)
        params = {**common_params, "areaCode": area_code, "numOfRows": "100"}
        response = session.get(f"{BASE_URL}areaCode2", params=params)
        response.raise_for_status()
        data = response.json()
        items = data.get('response', {}).get('body', {}).get('items', {}).get('item', [])
        sigungu_names = [item['name'] for item in items]
        return gr.update(choices=["전체"] + sigungu_names, value="전체", interactive=True)
    except Exception as e:
        print(f"[update_sigungu_dropdown error] {e}")
        return gr.update(choices=[], interactive=False)

def update_page_view(area_name, sigungu_name, category_name, page_to_go):
    """페이지네이션의 핵심 로직: 모든 필터를 적용하여 페이지 데이터 로드 및 UI 업데이트"""
    try:
        page_to_go = int(page_to_go)
        area_code = AREA_CODES.get(area_name)
        content_type_id = CONTENT_TYPE_CODES.get(category_name)

        params = {**common_params, "areaCode": area_code, "numOfRows": ROWS_PER_PAGE, "pageNo": page_to_go}
        if sigungu_name and sigungu_name != "전체":
            sigungu_response = session.get(f"{BASE_URL}areaCode2", params={**common_params, "areaCode": area_code, "numOfRows": "100"})
            sigungu_data = sigungu_response.json()
            sigungu_items = sigungu_data.get('response', {}).get('body', {}).get('items', {}).get('item', [])
            sigungu_code = next((item['code'] for item in sigungu_items if item['name'] == sigungu_name), None)
            if sigungu_code: params["sigunguCode"] = sigungu_code
        if content_type_id:
            params["contentTypeId"] = content_type_id

        response = session.get(f"{BASE_URL}areaBasedList2", params=params)
        response.raise_for_status()
        data = response.json()
        body = data.get('response', {}).get('body', {})
        
        items = body.get('items', {}).get('item', [])
        if isinstance(items, dict): items = [items]
        places_info = {item['title']: (item['contentid'], item['contenttypeid']) for item in items if 'title' in item}
        
        total_count = body.get('totalCount', 0)
        total_pages = math.ceil(total_count / ROWS_PER_PAGE)
        
        half_window = PAGE_WINDOW_SIZE // 2
        start_page = max(1, page_to_go - half_window)
        end_page = min(total_pages, start_page + PAGE_WINDOW_SIZE - 1)
        if end_page - start_page + 1 < PAGE_WINDOW_SIZE:
            start_page = max(1, end_page - PAGE_WINDOW_SIZE + 1)

        page_numbers_to_show = list(range(start_page, end_page + 1))

        radio_update = gr.update(choices=list(places_info.keys()), value=None)
        pagination_numbers_update = gr.update(choices=page_numbers_to_show, value=page_to_go)
        first_btn_update = gr.update(interactive=page_to_go > 1)
        prev_btn_update = gr.update(interactive=page_to_go > 1)
        next_btn_update = gr.update(interactive=page_to_go < total_pages)
        last_btn_update = gr.update(interactive=page_to_go < total_pages)
        pagination_row_update = gr.update(visible=total_pages > 1)

        return area_name, sigungu_name, category_name, page_to_go, total_pages, places_info, radio_update, pagination_numbers_update, first_btn_update, prev_btn_update, next_btn_update, last_btn_update, pagination_row_update

    except Exception as e:
        print(f"[update_page_view error] {e}")
        return area_name, sigungu_name, category_name, 1, 1, {}, gr.update(choices=[], value=None), gr.update(choices=[], value=None), gr.update(interactive=False), gr.update(interactive=False), gr.update(interactive=False), gr.update(interactive=False), gr.update(visible=False)

# --- 상세 정보 가공 및 호출 함수들 (생략) ---
def get_details(selected_title, places_info):
    if not selected_title or not places_info:
        return ("",) * 6
    
    if selected_title not in places_info:
        return ("선택된 항목을 찾을 수 없습니다.",) * 6

    content_id, content_type_id = places_info[selected_title]
    results = [""] * 6
    apis_to_call = [("detailCommon2", {"contentId": content_id}), ("detailIntro2", {"contentId": content_id, "contentTypeId": content_type_id}), ("detailInfo2", {"contentId": content_id, "contentTypeId": content_type_id})]
    
    for i, (api_name, specific_params) in enumerate(apis_to_call):
        try:
            params = {**common_params, **specific_params}
            response = session.get(f"{BASE_URL}{api_name}", params=params)
            response.raise_for_status()
            
            if not response.text or not response.text.strip():
                raise ValueError("API 응답이 비어 있습니다.")

            response_json = response.json()
            
            header = response_json.get('response', {}).get('header', {})
            if header.get('resultCode') != '0000':
                # API 자체 에러 발생 시, 포맷하지 않고 원본 JSON을 보여줌
                pretty_output = json.dumps(response_json, indent=2, ensure_ascii=False)
            else:
                # 성공 시에만 필터링 및 클린 포맷 적용
                pretty_output = format_json_to_clean_string(response_json)

            results[i * 2] = json.dumps(response_json, indent=2, ensure_ascii=False)
            results[i * 2 + 1] = pretty_output

        except json.JSONDecodeError as json_e:
            error_msg = f"{api_name} 처리 중 JSON 오류: {json_e}\nAPI 응답 내용:\n{response.text[:500]}"
            results[i * 2] = error_msg
            results[i * 2 + 1] = "정보를 가져오는 데 실패했습니다."
        except Exception as e:
            error_msg = f"{api_name} 처리 중 오류: {e}"
            results[i * 2] = error_msg
            results[i * 2 + 1] = "정보를 가져오는 데 실패했습니다."
            
    return tuple(results)

def export_to_csv(area_name, sigungu_name, category_name, progress=gr.Progress()):
    """검색된 모든 결과를 API 응답 순서에 따른 동적 컬럼 CSV 파일로 저장합니다."""
    if not area_name:
        gr.Warning("지역을 먼저 선택해주세요.")
        return None

    progress(0, desc="전체 데이터 개수 확인 중...")

    try:
        # 1. 전체 아이템 개수 확인
        area_code = AREA_CODES.get(area_name)
        content_type_id = CONTENT_TYPE_CODES.get(category_name)
        
        base_list_params = {**common_params, "areaCode": area_code, "numOfRows": 1, "pageNo": 1}
        if sigungu_name and sigungu_name != "전체":
            sigungu_response = session.get(f"{BASE_URL}areaCode2", params={**common_params, "areaCode": area_code, "numOfRows": "100"})
            sigungu_data = sigungu_response.json()
            sigungu_items = sigungu_data.get('response', {}).get('body', {}).get('items', {}).get('item', [])
            sigungu_code = next((item['code'] for item in sigungu_items if item['name'] == sigungu_name), None)
            if sigungu_code: base_list_params["sigunguCode"] = sigungu_code
        if content_type_id:
            base_list_params["contentTypeId"] = content_type_id

        response = session.get(f"{BASE_URL}areaBasedList2", params=base_list_params)
        response.raise_for_status()
        total_count = response.json().get('response', {}).get('body', {}).get('totalCount', 0)

        if total_count == 0:
            gr.Info("내보낼 데이터가 없습니다.")
            return None

        # 2. 모든 기본 아이템 정보 수집
        all_basic_items = []
        num_of_rows = 100
        total_pages = math.ceil(total_count / num_of_rows)
        
        for page_no in progress.tqdm(range(1, total_pages + 1), desc="관광지 목록 수집 중"):
            base_list_params.update({"numOfRows": num_of_rows, "pageNo": page_no})
            response = session.get(f"{BASE_URL}areaBasedList2", params=base_list_params)
            response.raise_for_status()
            items = response.json().get('response', {}).get('body', {}).get('items', {}).get('item', [])
            if isinstance(items, dict): items = [items]
            all_basic_items.extend(items)

        # 3. 각 아이템의 상세 정보 조회 및 데이터 재구성
        all_item_details = []
        ordered_headers = []
        seen_keys = set()

        def add_key_to_header(key):
            if is_key_excluded(key):
                return
            if key not in seen_keys:
                ordered_headers.append(key)
                seen_keys.add(key)

        for item in progress.tqdm(all_basic_items, desc="상세 정보 조회 및 데이터 구성 중"):
            content_id = item.get('contentid')
            content_type_id = item.get('contenttypeid')
            if not content_id:
                continue

            base_data = {}
            try:
                # 기본 정보와 공통, 소개 정보 수집
                base_data.update(item)
                for key in item.keys():
                    add_key_to_header(key)

                apis_to_process = [
                    ("detailCommon2", {**common_params, "contentId": content_id, "defaultYN": "Y", "firstImageYN": "Y", "areacodeYN": "Y", "catcodeYN": "Y", "addrinfoYN": "Y", "mapinfoYN": "Y", "overviewYN": "Y"}),
                    ("detailIntro2", {**common_params, "contentId": content_id, "contentTypeId": content_type_id}),
                ]

                for api_name, params in apis_to_process:
                    response = session.get(f"{BASE_URL}{api_name}", params=params)
                    response.raise_for_status()
                    if not response.text or not response.text.strip(): continue
                    
                    res = response.json()
                    res_items = res.get('response', {}).get('body', {}).get('items', {}).get('item', [])
                    if not res_items: continue
                    if isinstance(res_items, dict): res_items = [res_items]

                    for res_item in res_items:
                        base_data.update(res_item)
                        for key in res_item.keys():
                            add_key_to_header(key)
                
                # 반복 정보(detailInfo2) 처리
                detail_info_params = {**common_params, "contentId": content_id, "contentTypeId": content_type_id}
                response = session.get(f"{BASE_URL}detailInfo2", params=detail_info_params)
                response.raise_for_status()
                
                info_items = []
                if response.text and response.text.strip():
                    res = response.json()
                    info_items = res.get('response', {}).get('body', {}).get('items', {}).get('item', [])
                    if isinstance(info_items, dict): info_items = [info_items]

                if info_items:
                    for info_item in info_items:
                        # 각 반복 정보 아이템에 대해 행 추가
                        row_data = {**base_data, **info_item}
                        all_item_details.append(row_data)
                        for key in info_item.keys():
                            add_key_to_header(key)
                else:
                    # 반복 정보가 없으면 기본 정보만으로 행 추가
                    all_item_details.append(base_data)

            except Exception as detail_e:
                print(f"Error fetching details for content_id {content_id}: {detail_e}")
                continue
        
        if not all_item_details:
            gr.Info("상세 정보를 가져올 수 있는 데이터가 없습니다.")
            return None

        # 4. CSV 파일 생성
        progress(0.9, desc="CSV 파일 생성 중...")
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=ordered_headers, extrasaction='ignore')
        writer.writeheader()

        for item_data in all_item_details:
            cleaned_item = {}
            for k, v in item_data.items():
                if k == 'homepage':
                    # homepage 필드에서 URL 추출
                    match = re.search(r'href=["\\](["\\][^"\\]+)["\\]', str(v))
                    cleaned_item[k] = match.group(1) if match else clean_html(str(v))
                else:
                    # 다른 필드는 기존 방식대로 HTML 태그 제거
                    cleaned_item[k] = clean_html(v) if isinstance(v, str) else v
            writer.writerow(cleaned_item)
        
        csv_content = output.getvalue()
        output.close()
        
        encoded_content = csv_content.encode('utf-8-sig')

        with tempfile.NamedTemporaryFile(delete=False, mode='wb', suffix='.csv', prefix='tour_data_') as temp_f:
            temp_f.write(encoded_content)
            gr.Info("CSV 파일 생성이 완료되었습니다. 아래 링크를 클릭하여 다운로드하세요.")
            return temp_f.name

    except Exception as e:
        import traceback
        print(f"[export_to_csv error] {e}")
        traceback.print_exc()
        gr.Error(f"CSV 생성 중 오류가 발생했습니다: {e}")
        return None


# --- Gradio 인터페이스 구성 ---
with gr.Blocks(title="TourAPI 관광 정보 앱") as demo:
    gr.Markdown("## TourAPI를 활용한 관광 정보 조회")
    with gr.Tabs():
        with gr.TabItem("내 위치로 검색"):
            # ... (이전과 동일)
            places_info_state_nearby = gr.State({})
            with gr.Row():
                get_loc_button = gr.Button("내 위치 가져오기")
                lat_box, lon_box = gr.Textbox(label="위도", interactive=False), gr.Textbox(label="경도", interactive=False)
            search_button_nearby = gr.Button("이 좌표로 주변 관광지 검색", variant="primary")
            radio_list_nearby = gr.Radio(label="관광지 목록", interactive=True)
            with gr.Accordion("상세 정보 보기", open=False):
                common_raw_n, common_pretty_n = gr.Textbox(label="Raw JSON"), gr.Markdown()
                intro_raw_n, intro_pretty_n = gr.Textbox(label="Raw JSON"), gr.Markdown()
                info_raw_n, info_pretty_n = gr.Textbox(label="Raw JSON"), gr.Markdown()
            get_loc_button.click(fn=None, js=get_location_js, outputs=[lat_box, lon_box])
            search_button_nearby.click(fn=find_nearby_places, inputs=[lat_box, lon_box], outputs=[radio_list_nearby, places_info_state_nearby])
            radio_list_nearby.change(fn=get_details, inputs=[radio_list_nearby, places_info_state_nearby], outputs=[common_raw_n, common_pretty_n, intro_raw_n, intro_pretty_n, info_raw_n, info_pretty_n])

        with gr.TabItem("지역/카테고리별 검색"):
            # 상태 변수들
            current_area = gr.State(None)
            current_sigungu = gr.State(None)
            current_category = gr.State(None)
            current_page = gr.State(1)
            total_pages = gr.State(1)
            places_info_state_area = gr.State({})

            # UI 컴포넌트
            with gr.Row():
                area_dropdown = gr.Dropdown(label="지역", choices=list(AREA_CODES.keys()))
                sigungu_dropdown = gr.Dropdown(label="시군구", interactive=False)
                category_dropdown = gr.Dropdown(label="카테고리", choices=list(CONTENT_TYPE_CODES.keys()), value="전체")
            
            with gr.Row():
                search_by_area_btn = gr.Button("검색하기", variant="primary")
                export_csv_btn = gr.Button("CSV로 내보내기")

            radio_list_area = gr.Radio(label="관광지 목록", interactive=True)
            
            with gr.Row(visible=False) as pagination_row:
                first_page_btn = gr.Button("<< 맨 처음")
                prev_page_btn = gr.Button("< 이전")
                page_numbers_radio = gr.Radio(label="페이지", interactive=True, scale=3)
                next_page_btn = gr.Button("다음 >")
                last_page_btn = gr.Button("맨 끝 >>")
            
            csv_file_output = gr.File(label="다운로드", interactive=False)

            with gr.Accordion("상세 정보 보기", open=False):
                common_raw_a, common_pretty_a = gr.Textbox(label="Raw JSON"), gr.Markdown()
                intro_raw_a, intro_pretty_a = gr.Textbox(label="Raw JSON"), gr.Markdown()
                info_raw_a, info_pretty_a = gr.Textbox(label="Raw JSON"), gr.Markdown()
            
            # 이벤트 리스너
            outputs_for_page_change = [current_area, current_sigungu, current_category, current_page, total_pages, places_info_state_area, radio_list_area, page_numbers_radio, first_page_btn, prev_page_btn, next_page_btn, last_page_btn, pagination_row]
            
            area_dropdown.change(fn=update_sigungu_dropdown, inputs=area_dropdown, outputs=sigungu_dropdown)
            search_by_area_btn.click(fn=update_page_view, inputs=[area_dropdown, sigungu_dropdown, category_dropdown, gr.Number(value=1, visible=False)], outputs=outputs_for_page_change)
            
            export_csv_btn.click(fn=export_to_csv, inputs=[area_dropdown, sigungu_dropdown, category_dropdown], outputs=csv_file_output)

            # 페이지네이션 버튼 이벤트
            page_inputs = [current_area, current_sigungu, current_category]
            first_page_btn.click(lambda area, sigungu, cat: update_page_view(area, sigungu, cat, 1), inputs=page_inputs, outputs=outputs_for_page_change)
            prev_page_btn.click(lambda area, sigungu, cat, page: update_page_view(area, sigungu, cat, page - 1), inputs=page_inputs + [current_page], outputs=outputs_for_page_change)
            next_page_btn.click(lambda area, sigungu, cat, page: update_page_view(area, sigungu, cat, page + 1), inputs=page_inputs + [current_page], outputs=outputs_for_page_change)
            last_page_btn.click(lambda area, sigungu, cat, pages: update_page_view(area, sigungu, cat, pages), inputs=page_inputs + [total_pages], outputs=outputs_for_page_change)
            page_numbers_radio.select(update_page_view, inputs=page_inputs + [page_numbers_radio], outputs=outputs_for_page_change)

            radio_list_area.change(fn=get_details, inputs=[radio_list_area, places_info_state_area], outputs=[common_raw_a, common_pretty_a, intro_raw_a, intro_pretty_a, info_raw_a, info_pretty_a])

if __name__ == "__main__":
    # 필수 라이브러리 설치 여부 확인
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("필수 라이브러리가 설치되지 않았습니다.")
        print("pip install python-dotenv")
        exit()
    
    # .env 파일에서 API 키 로드 확인
    load_dotenv()
    if not os.getenv("TOUR_API_KTY"):
        print("TourAPI 키가 설정되지 않았습니다. .env 파일에 TOUR_API_KTY를 추가해주세요.")
        exit()

    demo.launch(debug=True)
