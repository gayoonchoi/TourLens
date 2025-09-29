import requests
import os

# 사용자가 제공한 API 키
SEOUL_TOUR_API_KEY = os.getenv("SEOUL_TOUR_API_KEY")
BASE_URL = f"http://openapi.seoul.go.kr:8088/{SEOUL_TOUR_API_KEY}/json/TbVwAttractions"

def _process_raw_items(raw_items):
    """API에서 받은 원본 아이템 리스트를 가공하고, 원본도 함께 보존합니다."""
    ko_items = [item for item in raw_items if item.get('LANG_CODE_ID') == 'ko']
    
    items_to_process = ko_items if ko_items else list({item['POST_SN']: item for item in raw_items}.values())

    final_items = []
    for item in items_to_process:
        processed_item = {
            'contentid': item.get('POST_SN'),
            'title': item.get('POST_SJ'),
            'addr1': item.get('NEW_ADDRESS') or item.get('ADDRESS'),
            'tel': item.get('CMMN_TELNO'),
            'tags': item.get('TAG'),
            'firstimage': None, 
            'firstimage2': None,
            'mapx': None,
            'mapy': None
        }
        # 원본 데이터와 가공된 데이터를 함께 저장
        final_items.append({
            'raw': item,
            'processed': processed_item
        })
    return final_items

def fetch_attractions(page_no=1, num_of_rows=12):
    """
    서울 열린 데이터 광장 API를 사용하여 특정 페이지의 관광 명소 정보를 가져옵니다.
    """
    start_index = (page_no - 1) * num_of_rows + 1
    end_index = page_no * num_of_rows
    url = f"{BASE_URL}/{start_index}/{end_index}/"

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        if 'TbVwAttractions' not in data or 'row' not in data['TbVwAttractions']:
            if 'RESULT' in data:
                print(f"API Error: {data['RESULT'].get('CODE')} - {data['RESULT'].get('MESSAGE')}")
            else:
                print("API 응답에서 'TbVwAttractions' 또는 'row'를 찾을 수 없습니다.")
            return {'items': [], 'totalCount': 0}

        total_count = data['TbVwAttractions'].get('list_total_count', 0)
        processed_items = _process_raw_items(data['TbVwAttractions']['row'])

        return {
            'items': processed_items,
            'totalCount': total_count
        }

    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        return {'items': [], 'totalCount': 0}
    except Exception as e:
        print(f"An error occurred: {e}")
        return {'items': [], 'totalCount': 0}

import math

def get_all_seoul_data():
    """
    서울 열린 데이터 광장 API에서 페이지네이션을 통해 모든 관광 명소 데이터를 가져옵니다.
    필터링을 위한 전체 데이터 소스로 사용됩니다.
    """
    all_items = []
    page_size = 1000  # API가 한 번에 반환할 수 있는 최대 레코드 수
    start_index = 1

    # 1. 첫 호출로 전체 카운트 가져오기
    try:
        initial_url = f"{BASE_URL}/{start_index}/{start_index}/"
        response = requests.get(initial_url)
        response.raise_for_status()
        data = response.json()
        
        if 'TbVwAttractions' not in data or 'list_total_count' not in data['TbVwAttractions']:
            print("API 응답에서 전체 데이터 수를 가져올 수 없습니다.")
            return []
            
        total_count = data['TbVwAttractions']['list_total_count']
        if total_count == 0:
            return []

    except requests.exceptions.RequestException as e:
        print(f"Initial request failed: {e}")
        return []
    except Exception as e:
        print(f"An error occurred during initial fetch: {e}")
        return []

    # 2. 전체 카운트를 기반으로 모든 페이지 순회
    total_pages = math.ceil(total_count / page_size)
    
    for page in range(total_pages):
        start = page * page_size + 1
        end = start + page_size - 1
        url = f"{BASE_URL}/{start}/{end}/"
        
        print(f"Fetching page {page + 1}/{total_pages} (rows {start}-{end})...")
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            if 'TbVwAttractions' in data and 'row' in data['TbVwAttractions']:
                all_items.extend(data['TbVwAttractions']['row'])
            else:
                # 한 페이지 실패 시 다음 페이지로 계속 진행
                print(f"Warning: Page {page + 1} fetch failed or returned no data.")

        except requests.exceptions.RequestException as e:
            print(f"Request for page {page + 1} failed: {e}")
            continue # 오류 발생 시 다음 페이지로 넘어감
        except Exception as e:
            print(f"An error occurred on page {page + 1}: {e}")
            continue

    print(f"Total items fetched: {len(all_items)}")
    return _process_raw_items(all_items)

if __name__ == '__main__':
    # 모듈 직접 실행 시 테스트
    all_data = get_all_seoul_data(limit=5)
    if all_data:
        print(f"Successfully fetched {len(all_data)} items.")
        for attraction in all_data:
            print(attraction)
    else:
        print("Failed to fetch data or no data available.")