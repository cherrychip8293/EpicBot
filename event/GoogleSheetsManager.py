import logging
import re
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from googleapiclient.errors import HttpError
from datetime import datetime

class GoogleSheetsManager:
    """
    Google Sheets와의 상호작용을 관리하는 클래스.
    """

    def __init__(self, service_account_file, spreadsheet_id):
        """
        Google Sheets API 초기화 및 인증.
        :param service_account_file: 서비스 계정 키 파일 경로
        :param spreadsheet_id: 작업할 Google Sheets 문서 ID
        """
        self.spreadsheet_id = spreadsheet_id
        self.scopes = ['https://www.googleapis.com/auth/spreadsheets']
        self.credentials = Credentials.from_service_account_file(service_account_file, scopes=self.scopes)
        self.service = build('sheets', 'v4', credentials=self.credentials)

    def _authenticate(self):
        from google.oauth2.service_account import Credentials

        creds = Credentials.from_service_account_file(
            self.service_account_file,
            scopes=["https://www.googleapis.com/auth/spreadsheets"]
        )
        return build('sheets', 'v4', credentials=creds)

    def get_sheet_names(self):
        """
        스프레드시트의 모든 시트 이름을 반환합니다.
        """
        try:
            spreadsheet = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
            sheet_names = [sheet['properties']['title'] for sheet in spreadsheet.get('sheets', [])]
            return sheet_names
        except Exception as e:
            logging.error(f"시트 이름 가져오기 중 오류 발생: {e}", exc_info=True)
            return None

    def update_participation_and_wins(self, sheet_name, participants, action, 승리팀):
        try:
            # D, J, L 열 데이터를 개별적으로 가져옵니다.
            nicknames = self.get_values(sheet_name=sheet_name, range_notation="D:D")
            participation_counts = self.get_values(sheet_name=sheet_name, range_notation="J:J")
            win_counts = self.get_values(sheet_name=sheet_name, range_notation="L:L")

            def safe_int_conversion(value):
                if value is None:
                    return 0
                if isinstance(value, (int, float)):
                    return int(value)
                if isinstance(value, str):
                    try:
                        numeric_value = float(value) if '.' in value else int(value)
                        return int(numeric_value)
                    except ValueError:
                        return 0
                return 0

            for participant in participants:
                for row_idx, row in enumerate(nicknames):
                    if len(row) > 0 and row[0].strip() == participant["게임 닉네임"].strip():
                        # 참여 횟수 업데이트
                        participation_value = (
                            participation_counts[row_idx][0] if len(participation_counts) > row_idx 
                            and len(participation_counts[row_idx]) > 0 else None
                        )
                        participation_count = safe_int_conversion(participation_value) + 1
                        self.update_cell(sheet_name, "J", row_idx + 1, [participation_count])

                        # 우승 횟수 업데이트
                        if action == "승리자" and 승리팀 == participant["게임 닉네임"]:
                            win_value = (
                                win_counts[row_idx][0] if len(win_counts) > row_idx 
                                and len(win_counts[row_idx]) > 0 else None
                            )
                            win_count = safe_int_conversion(win_value) + 1
                            self.update_cell(sheet_name, "L", row_idx + 1, [win_count])
                        break
        except Exception as e:
            print(f"참여/우승 횟수 업데이트 오류: {e}")

    def clean_nickname(self, nickname: str) -> str:
        """
        닉네임에서 숫자, 성별 구분 텍스트, 롤 티어 제거
        """
        nickname = re.sub(r"\d", "", nickname)  # 숫자 제거
        nickname = re.sub(r"(?:남|여)", "", nickname)  # 남/여 제거
        nickname = re.sub(r"(?:B|S|G|P|E|D|M|GM|C)", "", nickname)  # 롤 티어 제거
        nickname = nickname.split('#')[0]  # # 태그 제거
        return nickname.strip()

    def update_cell(self, sheet_name, start_column, start_row, values):
        """
        특정 위치에서 데이터를 업데이트합니다.
        :param sheet_name: 시트 이름
        :param start_column: 시작 열 (예: W)
        :param start_row: 시작 행 (예: 5)
        :param values: 입력할 데이터 리스트
        """
        try:
            def safe_convert(value):
                if isinstance(value, (int, float)):
                    return value  # 숫자는 그대로 반환
                if isinstance(value, str):
                    try:
                        if value.strip().isdigit():
                            return int(value)  # 숫자 문자열을 정수로 변환
                        if '.' in value and value.replace('.', '', 1).isdigit():
                            return float(value)  # 소수점 포함 숫자 문자열을 부동소수점으로 변환
                    except ValueError:
                        pass
                return value  # 변환 불가능한 경우 원본 값 반환

            # 값 변환
            formatted_values = [[safe_convert(v) for v in row] for row in values]

            # Google Sheets 범위 지정
            range_notation = f"{sheet_name}!{start_column}{start_row}"

            # API 요청
            response = self.service.spreadsheets().values().update(
                spreadsheetId=self.spreadsheet_id,
                range=range_notation,
                valueInputOption="USER_ENTERED",  # 자동 형식 변환
                body={'values': formatted_values}
            ).execute()

            # 업데이트 후 값 검증
            updated_values = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_notation
            ).execute()

        except Exception as e:
            print(f"Google Sheets 업데이트 중 오류 발생: {e}")
            raise

    def append_row(self, sheet_name, values):
        """
        특정 시트에 데이터를 추가합니다.
        :param sheet_name: 데이터를 추가할 시트 이름
        :param values: 추가할 데이터 리스트 (한 행)
        """
        try:
            body = {
                'values': [values]
            }
            self.service.spreadsheets().values().append(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!A:Z",  # 데이터를 추가할 범위
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body=body
            ).execute()
        except Exception as e:
            print(f"Google Sheets 데이터 추가 중 오류 발생: {e}")

    def get_values(self, sheet_name, range_notation):
        """
        Google Sheets에서 특정 범위의 값을 가져옵니다.
        :param sheet_name: 시트 이름
        :param range_notation: 가져올 데이터 범위 (예: "A1:Z100")
        :return: 가져온 데이터 리스트
        """
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=f"{sheet_name}!{range_notation}"
            ).execute()
            values = result.get("values", [])
            return values
        except Exception as e:
            print(f"Error retrieving values: {e}")
            raise
        
    def export_sheet_as_xlsx(self, sheet_name, file_path):
        """
        특정 시트를 .xlsx 파일로 내보냅니다.
        :param sheet_name: 시트 이름
        :param file_path: 저장할 파일 경로
        """
        try:
            # 데이터 가져오기
            values = self.get_values(sheet_name=sheet_name, range_notation="A:Z")
            if not values:
                raise ValueError(f"시트 '{sheet_name}'에서 데이터를 가져오지 못했습니다.")

            # xlsx 저장
            import openpyxl
            workbook = openpyxl.Workbook()
            sheet = workbook.active
            sheet.title = sheet_name

            for row_idx, row in enumerate(values, start=1):
                for col_idx, value in enumerate(row, start=1):
                    sheet.cell(row=row_idx, column=col_idx, value=value)

            workbook.save(file_path)
        except Exception as e:
            print(f"시트를 내보내는 중 오류 발생: {e}")
            raise

    def delete_sheet(self, sheet_name):
        """
        Google Sheets에서 특정 시트를 삭제합니다.
        :param sheet_name: 삭제할 시트 이름
        """
        try:
            # 시트 메타데이터를 가져옵니다.
            sheets_metadata = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
            sheet_id = next(
                sheet['properties']['sheetId']
                for sheet in sheets_metadata['sheets']
                if sheet['properties']['title'] == sheet_name
            )

            # 시트 삭제 요청
            delete_request = {
                'requests': [
                    {
                        'deleteSheet': {
                            'sheetId': sheet_id
                        }
                    }
                ]
            }
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body=delete_request
            ).execute()
        except Exception as e:
            print(f"Google Sheets 시트 삭제 중 오류 발생: {e}")

    def increment_sheet_value(self, sheet_name, nickname_column, target_column, nickname, increment_value=1):
        """
        Google Sheets에서 특정 멤버의 데이터를 업데이트합니다.
        :param sheet_name: 시트 이름
        :param nickname_column: 닉네임이 있는 열 (예: "D")
        :param target_column: 업데이트할 열 (예: "J")
        :param nickname: 업데이트할 닉네름
        :param increment_value: 증가시킬 값 (기본: 1)
        """
        try:
            nicknames = self.get_values(sheet_name=sheet_name, range_notation=f"{nickname_column}:{nickname_column}")
            for row_idx, row in enumerate(nicknames):
                if len(row) > 0 and row[0].strip() == nickname.strip():
                    # 해당 행의 기존 값을 가져옵니다.
                    current_values = self.get_values(
                        sheet_name=sheet_name,
                        range_notation=f"{target_column}{row_idx + 1}:{target_column}{row_idx + 1}"
                    )
                    current_value = int(current_values[0][0]) if current_values and current_values[0] else 0

                    # 값을 증가시키고 업데이트합니다.
                    new_value = current_value + increment_value
                    self.update_cell(sheet_name, target_column, row_idx + 1, [new_value])
                    return
            print(f"'{sheet_name}' 시트에서 닉네임 '{nickname}'을 찾을 수 없습니다.")
        except Exception as e:
            print(f"Google Sheets 업데이트 중 오류 발생: {e}")


    def copy_sheet(self, source_sheet_name):
        """
        특정 시트를 복사하고 새로운 시트 이름을 설정합니다.
        :param source_sheet_name: 복사할 원본 시트 이름
        :return: 새 시트 이름
        """
        try:
            # 시트 메타데이터 가져오기
            sheets_metadata = self.service.spreadsheets().get(spreadsheetId=self.spreadsheet_id).execute()
            source_sheet_id = next(
                sheet['properties']['sheetId']
                for sheet in sheets_metadata['sheets']
                if sheet['properties']['title'] == source_sheet_name
            )

            # 시트 복사
            copy_request = {
                'destinationSpreadsheetId': self.spreadsheet_id
            }
            response = self.service.spreadsheets().sheets().copyTo(
                spreadsheetId=self.spreadsheet_id,
                sheetId=source_sheet_id,
                body=copy_request
            ).execute()

            # 새 시트 이름 설정 (유효한 제목으로 변환)
            new_sheet_id = response['sheetId']
            new_sheet_name = f"내전-{datetime.now().strftime('%Y-%m-%d')}".replace("/", "-")
            update_request = {
                'requests': [
                    {
                        'updateSheetProperties': {
                            'properties': {
                                'sheetId': new_sheet_id,
                                'title': new_sheet_name
                            },
                            'fields': 'title'
                        }
                    }
                ]
            }
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.spreadsheet_id,
                body=update_request
            ).execute()

            return new_sheet_name
        except Exception as e:
            print(f"시트 복사 중 오류 발생: {e}")
            return None