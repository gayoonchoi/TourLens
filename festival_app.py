import os
import gradio as gr
from dotenv import load_dotenv
from serpapi import NaverSearch # SerpApi 라이브러리 사용
import re

# .env 파일에서 환경 변수 로드
load_dotenv()

# SerpApi 키 확인
SERPAPI_API_KEY = os.getenv("SERPAPI_API_KEY")

if not SERPAPI_API_KEY:
    raise ValueError("SerpApi API 키를 .env 파일에 SERPAPI_API_KEY로 설정해야 합니다.")

def find_festivals() -> gr.Dropdown:
    """'2025 서울 행사'를 SerpApi로 검색하여 '이런 축제 어때요?' 목록을 반환합니다."""
    print("SerpApi로 초기 검색을 시작합니다: '2025 서울 행사'")
    
    try:
        # SerpApi를 사용하여 Naver 검색
        params = {
            "query": "2025 서울 행사",
            "api_key": SERPAPI_API_KEY
        }
        search = NaverSearch(params)
        results = search.get_dict()

        festival_titles = []
        # SerpApi는 '이런 축제 어때요?' 정보를 'local_results' 키 안에 'places' 리스트로 제공
        if "local_results" in results and "places" in results["local_results"]:
            places = results["local_results"]["places"]
            print(f"SerpApi의 'local_results'에서 {len(places)}개의 장소/행사를 찾았습니다.")
            for place in places:
                title = place.get("title", "")
                if title and title not in festival_titles:
                    festival_titles.append(title)
        
        if not festival_titles:
            print("SerpApi 검색 결과에서 'local_results' (축제 목록)을 찾지 못했습니다.")
            return gr.Dropdown(choices=[], label="축제를 찾지 못했습니다.", value=None)

        print(f"찾은 축제 목록: {festival_titles}")
        return gr.Dropdown(choices=festival_titles, label="🎉 이런 축제 어때요?", info="관심 있는 축제를 선택하세요.", interactive=True, value=None)

    except Exception as e:
        print(f"오류 발생: {e}")
        return gr.Dropdown(choices=[], label="API 오류 발생", value=None)

def get_festival_info(festival_name: str) -> tuple[str, str]:
    """선택된 축제 이름으로 상세 정보를 검색하고 '개요'와 '소개'를 분리하여 반환합니다."""
    if not festival_name:
        return "축제를 선택해주세요.", ""

    query = f'"{festival_name}" 기본정보'
    print(f"SerpApi로 상세 정보 검색을 시작합니다: {query}")
    
    try:
        params = {
            "query": query,
            "api_key": SERPAPI_API_KEY
        }
        search = NaverSearch(params)
        results = search.get_dict()
        
        overview_text = "정보를 찾을 수 없습니다."
        introduction_text = "정보를 찾을 수 없습니다."

        # 상세 정보는 'knowledge_graph'에 주로 표시됨
        if "knowledge_graph" in results:
            kg = results["knowledge_graph"]
            
            # 1. 개요(Overview) 정보 추출
            overview_parts = []
            # kg에 있는 모든 정보를 순회하며 텍스트로 만듦
            for key, value in kg.items():
                if isinstance(value, str) and key not in ["title", "description"]:
                     overview_parts.append(f"{key.capitalize()}: {value}")
            
            # 정보가 있다면 개요 텍스트 생성
            if overview_parts:
                 overview_text = "\n".join(overview_parts)
            else:
                 overview_text = "개요 정보를 찾을 수 없습니다."

            # 2. 소개(Introduction) 정보 추출
            # 'description' 키에 소개 내용이 있을 가능성이 높음
            if "description" in kg:
                introduction_text = kg["description"]
            else:
                introduction_text = "소개 정보를 찾을 수 없습니다."

        else:
            print(f"'{query}'에 대한 knowledge_graph 결과를 찾지 못했습니다.")

        print(f"추출된 개요: {overview_text}")
        print(f"추출된 소개: {introduction_text}")
        return overview_text, introduction_text

    except Exception as e:
        print(f"오류 발생: {e}")
        return f"오류 발생: {e}", ""

# Gradio UI 구성
with gr.Blocks(theme=gr.themes.Soft(), title="서울 문화 축제 정보") as demo:
    gr.Markdown(
        '''
        # 서울 문화 축제 정보 🎊
        '2025 서울 행사' 검색 결과를 바탕으로 서울의 다양한 문화 축제 정보를 찾아드립니다.
        '''
    )
    
    with gr.Row():
        search_button = gr.Button("🎉 축제 검색 시작", variant="primary", scale=1)
        festival_dropdown = gr.Dropdown(label="축제 목록", info="먼저 '축제 검색 시작' 버튼을 눌러주세요.", interactive=False, scale=3)

    with gr.Blocks():
        gr.Markdown("### 📜 축제 상세 정보")
        with gr.Row():
            overview_output = gr.Textbox(label="개요", lines=10, interactive=False)
            introduction_output = gr.Textbox(label="소개", lines=10, interactive=False)

    # 이벤트 리스너 연결
    search_button.click(
        fn=find_festivals,
        inputs=[],
        outputs=[festival_dropdown]
    )
    
    festival_dropdown.change(
        fn=get_festival_info,
        inputs=[festival_dropdown],
        outputs=[overview_output, introduction_output]
    )

if __name__ == "__main__":
    demo.launch()