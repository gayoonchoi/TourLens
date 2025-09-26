import gradio as gr
import os
from dotenv import load_dotenv
import glob
import tempfile

# .env 파일을 최상단에서 로드
load_dotenv()

# --- 시작 시 임시 이미지 폴더 정리 ---
# 이 부분은 사용자의 로컬 경로에 의존하므로, 스크립트가 실행되는 위치를 기준으로 상대 경로를 사용하도록 수정합니다.
image_temp_dir = "image_temp"
if os.path.exists(image_temp_dir):
    files_to_delete = glob.glob(os.path.join(image_temp_dir, '*.png'))
    for f in files_to_delete:
        try:
            os.remove(f)
        except OSError as e:
            print(f"Error removing file {f}: {e}")

# --- 분리된 모듈에서 기능들을 가져옴 ---
from modules.location_search.location import get_location_js
from modules.location_search.search import find_nearby_places
from modules.area_search.controls import (
    AREA_CODES, CONTENT_TYPE_CODES, update_sigungu_dropdown
)
from modules.area_search.search import update_page_view
from modules.area_search.details import get_details
from modules.area_search.export import export_to_csv
from modules.trend_analyzer import (
    generate_trends_from_area_search,
    generate_trends_from_location_search
)


# --- Gradio 인터페이스 구성 ---
with gr.Blocks(title="TourAPI 관광 정보 앱") as demo:
    gr.Markdown("## TourAPI를 활용한 관광 정보 조회")
    with gr.Tabs():
        # "내 위치로 검색" 탭
        with gr.TabItem("내 위치로 검색"):
            places_info_state_nearby = gr.State({})
            with gr.Row():
                get_loc_button = gr.Button("내 위치 가져오기")
                lat_box, lon_box = gr.Textbox(label="위도", interactive=False), gr.Textbox(label="경도", interactive=False)
            
            with gr.Row():
                search_button_nearby = gr.Button("이 좌표로 주변 관광지 검색", variant="primary")
                run_trend_btn_nearby = gr.Button("현재 목록 트렌드 저장하기")

            radio_list_nearby = gr.Radio(label="관광지 목록", interactive=True)
            status_output_nearby = gr.Textbox(label="작업 상태", interactive=False)
            
            with gr.Accordion("상세 정보 보기", open=False):
                common_raw_n, common_pretty_n = gr.Textbox(label="Raw JSON"), gr.Markdown()
                intro_raw_n, intro_pretty_n = gr.Textbox(label="Raw JSON"), gr.Markdown()
                info_raw_n, info_pretty_n = gr.Textbox(label="Raw JSON"), gr.Markdown()
            
            # 이벤트 리스너
            get_loc_button.click(fn=None, js=get_location_js, outputs=[lat_box, lon_box])
            search_button_nearby.click(fn=find_nearby_places, inputs=[lat_box, lon_box], outputs=[radio_list_nearby, places_info_state_nearby])
            run_trend_btn_nearby.click(fn=generate_trends_from_location_search, inputs=places_info_state_nearby, outputs=status_output_nearby)
            radio_list_nearby.change(fn=get_details, inputs=[radio_list_nearby, places_info_state_nearby], outputs=[common_raw_n, common_pretty_n, intro_raw_n, intro_pretty_n, info_raw_n, info_pretty_n])

        # "지역/카테고리별 검색" 탭
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
                run_trend_btn_area = gr.Button("현재 목록 트렌드 저장하기")

            radio_list_area = gr.Radio(label="관광지 목록", interactive=True)
            
            with gr.Row(visible=False) as pagination_row:
                first_page_btn = gr.Button("<< 맨 처음")
                prev_page_btn = gr.Button("< 이전")
                page_numbers_radio = gr.Radio(label="페이지", interactive=True, scale=3)
                next_page_btn = gr.Button("다음 >")
                last_page_btn = gr.Button("맨 끝 >>")
            
            # 출력 컴포넌트
            csv_file_output = gr.File(label="다운로드", interactive=False)
            status_output_area = gr.Textbox(label="작업 상태", interactive=False)

            with gr.Accordion("상세 정보 보기", open=False):
                common_raw_a, common_pretty_a = gr.Textbox(label="Raw JSON"), gr.Markdown()
                intro_raw_a, intro_pretty_a = gr.Textbox(label="Raw JSON"), gr.Markdown()
                info_raw_a, info_pretty_a = gr.Textbox(label="Raw JSON"), gr.Markdown()
            
            # 이벤트 리스너
            outputs_for_page_change = [current_area, current_sigungu, current_category, current_page, total_pages, places_info_state_area, radio_list_area, page_numbers_radio, first_page_btn, prev_page_btn, next_page_btn, last_page_btn, pagination_row]
            
            area_dropdown.change(fn=update_sigungu_dropdown, inputs=area_dropdown, outputs=sigungu_dropdown)
            search_by_area_btn.click(fn=update_page_view, inputs=[area_dropdown, sigungu_dropdown, category_dropdown, gr.Number(value=1, visible=False)], outputs=outputs_for_page_change)
            
            export_csv_btn.click(fn=export_to_csv, inputs=[area_dropdown, sigungu_dropdown, category_dropdown], outputs=csv_file_output)
            run_trend_btn_area.click(fn=generate_trends_from_area_search, inputs=[area_dropdown, sigungu_dropdown, category_dropdown], outputs=status_output_area)

            # 페이지네이션 버튼 이벤트
            page_inputs = [current_area, current_sigungu, current_category]
            first_page_btn.click(lambda area, sigungu, cat: update_page_view(area, sigungu, cat, 1), inputs=page_inputs, outputs=outputs_for_page_change)
            prev_page_btn.click(lambda area, sigungu, cat, page: update_page_view(area, sigungu, cat, page - 1), inputs=page_inputs + [current_page], outputs=outputs_for_page_change)
            next_page_btn.click(lambda area, sigungu, cat, page: update_page_view(area, sigungu, cat, page + 1), inputs=page_inputs + [current_page], outputs=outputs_for_page_change)
            last_page_btn.click(lambda area, sigungu, cat, pages: update_page_view(area, sigungu, cat, pages), inputs=page_inputs + [total_pages], outputs=outputs_for_page_change)
            page_numbers_radio.select(update_page_view, inputs=page_inputs + [page_numbers_radio], outputs=outputs_for_page_change)

            radio_list_area.change(fn=get_details, inputs=[radio_list_area, places_info_state_area], outputs=[common_raw_a, common_pretty_a, intro_raw_a, intro_pretty_a, info_raw_a, info_pretty_a])

# --- 애플리케이션 실행 ---
if __name__ == "__main__":
    # .env 파일 및 필수 키 확인
    if not os.getenv("TOUR_API_KTY"):
        print("TourAPI 키가 설정되지 않았습니다. .env 파일에 TOUR_API_KTY를 추가해주세요.")
        exit()
    if not os.getenv("NAVER_CLIENT_ID") or not os.getenv("NAVER_CLIENT_SECRET"):
        print("네이버 블로그 API 인증 정보가 .env 파일에 설정되지 않았습니다.")
        exit()
    if not os.getenv("NAVER_TREND_CLIENT_ID") or not os.getenv("NAVER_TREND_CLIENT_SECRET"):
        print("네이버 트렌드 API 인증 정보가 .env 파일에 설정되지 않았습니다.")
        exit()

    demo.launch(debug=True)
