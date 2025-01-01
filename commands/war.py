import logging
import time
from discord import app_commands
import discord
from discord.ext import commands
from event.GoogleSheetsManager import GoogleSheetsManager
from datetime import datetime
import os

# Google Sheets 설정
SERVICE_ACCOUNT_FILE = 'resources/service_account.json'
SPREADSHEET_ID = '1AYSWQwLOA-EvMJzJ7ros27OEzrTd2hERlI2WJX32RBE'

# Google Sheets 매니저 초기화
sheets_manager = GoogleSheetsManager(SERVICE_ACCOUNT_FILE, SPREADSHEET_ID)


class OngoingWar:
    def __init__(self):
        self.status = False
        self.participants = []
        self.current_sheet = None
        self.saved_files = []

    def reset(self):
        self.status = False
        self.participants = []
        self.current_sheet = None

ongoing_war = OngoingWar()

def initialize_ongoing_war():
    try:
        sheet_names = sheets_manager.get_sheet_names()
        if not sheet_names:
            return 0

        today_date = time.strftime('%Y-%m-%d')
        active_sheet_name = f"내전-{today_date}"

        if active_sheet_name in sheet_names:
            ongoing_war.status = True
            ongoing_war.current_sheet = active_sheet_name

            participants = sheets_manager.get_values(
                sheet_name=active_sheet_name, range_notation="X:X"
            )
            if participants is None:
                return 0

            valid_participants = []
            for idx, row in enumerate(participants, start=1):
                if row and len(row) == 1 and is_valid_participant(row[0].strip()):
                    valid_participants.append({"게임 닉네임": row[0].strip()})

            ongoing_war.participants = valid_participants
            logging.info(f"활성화된 시트 '{active_sheet_name}'의 참가자 수: {len(valid_participants)}명")
            return len(valid_participants)
        else:
            logging.info("내전 활성화 상태가 발견되지 않았습니다.")
            return 0
    except Exception as e:
        logging.error(f"내전 상태 복구 중 오류 발생: {e}", exc_info=True)
        return 0

def is_valid_participant(value):
    """
    주어진 데이터가 유효한 참가자 데이터인지 확인하는 함수.
    """
    if not value:
        return False
    if value.lower() in {"닉네임", "팀장지원금", "시트등록", "마감코드", "내전마감"}:
        return False
    if value.startswith("https://"):
        return False
    # 닉네임 형식 검사 (예: "이름#태그" 형식)
    if "#" in value and len(value.split("#")) == 2:
        return True
    return False


class JoinModal(discord.ui.Modal, title="내전 참여"):
    def __init__(self):
        super().__init__()

        # 닉네임 입력 필드 (태그 포함 안내 추가)
        self.nickname = discord.ui.TextInput(
            label="닉네임",
            placeholder="게임 닉네임#태그를 입력하세요 (예: Player#1234)",
            required=True
        )
        self.add_item(self.nickname)

        # 라인 입력 필드
        self.line = discord.ui.TextInput(
            label="라인",
            placeholder="주 라인을 입력하세요 (예: 탑, 미드, 정글, 원딜, 서폿)",
            required=True
        )
        self.add_item(self.line)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)

            nickname = self.nickname.value.strip()
            line = self.line.value.strip()

            logging.info(f"내전 참여 요청 - 게임 닉네임: {nickname}, 라인: {line}")

            # 멤버 시트에서 닉네임과 태그를 완전히 매칭
            member_data = sheets_manager.get_values(sheet_name="MEMBER", range_notation="C:D")
            member_row = next(
                (
                    row for row in member_data
                    if len(row) >= 2 and row[1].strip().lower() == nickname.lower()
                ),
                None
            )

            if not member_row:
                logging.warning(f"멤버 매칭 실패 - 닉네임: {nickname}")
                await interaction.followup.send("닉네임#태그를 찾을 수 없습니다.", ephemeral=True)
                return

            # 멤버 정보
            member_number = member_row[0].lstrip("'").strip()  # 순번
            full_nickname = member_row[1].strip()

            # 내전 시트에 데이터 추가
            if ongoing_war.current_sheet:
                sheet_data = sheets_manager.get_values(
                    sheet_name=ongoing_war.current_sheet,
                    range_notation="W5:Y100"
                )

                # 첫 번째 빈 행 찾기
                empty_row = next(
                    (idx for idx, row in enumerate(sheet_data, start=5) if not any(row)),
                    len(sheet_data) + 5
                )

                sheets_manager.update_cell(
                    sheet_name=ongoing_war.current_sheet,
                    start_column="W",
                    start_row=empty_row,
                    values=[[member_number, full_nickname, line]]
                )

                logging.info(f"참여자 정보 추가 - 행: {empty_row}, 데이터: [{member_number}, {full_nickname}, {line}]")
            else:
                logging.error("활성화된 내전 시트 없음")
                await interaction.followup.send("내전 시트가 활성화되지 않았습니다.", ephemeral=True)
                return

            # 참여자 목록 업데이트
            if not any(p['게임 닉네임'].lower() == full_nickname.lower() for p in ongoing_war.participants):
                ongoing_war.participants.append({
                    "게임 닉네임": full_nickname,
                    "라인": line
                })
                logging.info(f"현재 참여자 수: {len(ongoing_war.participants)}")
            else:
                logging.warning(f"중복 참여 요청 - 닉네임: {full_nickname}")

            await interaction.followup.send(f"{nickname} 님의 참여가 기록되었습니다.", ephemeral=True)
        except Exception as e:
            logging.error("참여 기록 중 오류 발생", exc_info=True)
            await interaction.followup.send(f"참여 기록 중 오류가 발생했습니다: {str(e)}", ephemeral=True)

class CancelModal(discord.ui.Modal, title="참여 취소"):
    def __init__(self):
        super().__init__()

        # 닉네임 입력 필드
        self.nickname = discord.ui.TextInput(
            label="닉네임",
            placeholder="참여 취소할 게임 닉네임을 입력하세요",
            required=True
        )
        self.add_item(self.nickname)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # 초기 응답 연장
            await interaction.response.defer(ephemeral=True)

            # 입력된 닉네임 가져오기
            nickname = self.nickname.value.strip()

            # 현재 활성화된 시트 확인
            if not ongoing_war.current_sheet:
                await interaction.followup.send("현재 활성화된 내전 시트가 없습니다.", ephemeral=True)
                return

            # 시트에서 데이터 검색
            member_data = sheets_manager.get_values(
                sheet_name=ongoing_war.current_sheet, range_notation="W:Y"
            )
            if not member_data:
                await interaction.followup.send("내전 시트에서 데이터를 가져올 수 없습니다.", ephemeral=True)
                return

            # 닉네임과 매칭되는 행 검색
            matching_row_index = None
            for idx, row in enumerate(member_data, start=1):  # 시작 인덱스 보정
                if len(row) >= 2 and row[1].strip().lower() == nickname.lower():
                    matching_row_index = idx
                    break

            if matching_row_index is None:
                await interaction.followup.send(
                    f"`{nickname}` 닉네임에 대한 참여 기록을 찾을 수 없습니다.",
                    ephemeral=True
                )
                return

            # Google Sheets에서 해당 데이터 비우기
            sheets_manager.update_cell(
                sheet_name=ongoing_war.current_sheet,
                start_column="W",
                start_row=matching_row_index,
                values=[["", "", ""]]  # W, X, Y 열 비우기
            )

            # 참여자 목록에서도 제거
            ongoing_war.participants = [
                p for p in ongoing_war.participants if p["게임 닉네임"].lower() != nickname.lower()
            ]

            await interaction.followup.send(
                f"`{nickname}` 님의 참여 기록이 성공적으로 취소되었습니다.",
                ephemeral=True
            )

        except Exception as e:
            logging.error("참여 취소 중 오류 발생: %s", e, exc_info=True)
            await interaction.followup.send(
                f"참여 취소 작업 중 오류가 발생했습니다: {str(e)}",
                ephemeral=True
            )

class WarView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        # 참여 버튼
        self.join_button = discord.ui.Button(
            label="내전 참여",
            style=discord.ButtonStyle.green,
            custom_id="persistent_join_button"
        )
        self.join_button.callback = self.join_callback
        self.add_item(self.join_button)

        # 참여 취소 버튼
        self.cancel_button = discord.ui.Button(
            label="참여 취소",
            style=discord.ButtonStyle.red,
            custom_id="persistent_cancel_button"
        )
        self.cancel_button.callback = self.cancel_callback
        self.add_item(self.cancel_button)

        # 인원 확인 버튼
        self.count_button = discord.ui.Button(
            label="인원",
            style=discord.ButtonStyle.gray,
            custom_id="persistent_count_button"
        )
        self.count_button.callback = self.count_callback
        self.add_item(self.count_button)

        # 관리 버튼 (관리자 전용)
        self.manage_button = discord.ui.Button(
            label="관리",
            style=discord.ButtonStyle.blurple,
            custom_id="persistent_manage_button"
        )
        self.manage_button.callback = self.manage_callback
        self.add_item(self.manage_button)

    async def join_callback(self, interaction: discord.Interaction):
        if not ongoing_war.status:
            await interaction.response.send_message("현재 활성화된 내전이 없습니다.", ephemeral=True)
            return
        modal = JoinModal()
        await interaction.response.send_modal(modal)

    async def cancel_callback(self, interaction: discord.Interaction):
        if not ongoing_war.status:
            await interaction.response.send_message("현재 활성화된 내전이 없습니다.", ephemeral=True)
            return
        modal = CancelModal()
        await interaction.response.send_modal(modal)

    async def manage_callback(self, interaction: discord.Interaction):
        # 관리자 권한 확인
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("이 버튼은 관리자만 사용할 수 있습니다.", ephemeral=True)
            return

        # 관리 인터페이스 표시
        manage_view = ManageView()
        await interaction.response.send_message("관리 옵션을 선택하세요:", view=manage_view, ephemeral=True)

    async def count_callback(self, interaction: discord.Interaction):
     logging.debug(f"현재 참여자 목록: {ongoing_war.participants}")
     if not ongoing_war.status:
        await interaction.response.send_message("현재 활성화된 내전이 없습니다.", ephemeral=True)
        return

     participant_count = len(ongoing_war.participants)
     logging.info(f"현재 참여 인원 확인 요청: {participant_count}명")
     await interaction.response.send_message(f"현재 참여 인원: {participant_count}명", ephemeral=True)


class CloseConfirmView(discord.ui.View):
    def __init__(self, original_interaction: discord.Interaction):
        super().__init__()
        self.original_interaction = original_interaction

    @discord.ui.button(label="확인", style=discord.ButtonStyle.red)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer(ephemeral=True)

            if ongoing_war.current_sheet:
                # 내전 기록 파일 생성
                file_name = f"내전기록_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.xlsx"
                file_path = os.path.join("records", file_name)
                sheets_manager.export_sheet_as_xlsx(ongoing_war.current_sheet, file_path)
                ongoing_war.saved_files.append(file_path)

                # 현재 시트 삭제
                sheets_manager.delete_sheet(ongoing_war.current_sheet)
                ongoing_war.reset()

                await interaction.followup.send("내전이 성공적으로 닫혔습니다.", ephemeral=True)
            else:
                await interaction.followup.send("현재 활성화된 내전이 없습니다.", ephemeral=True)

        except Exception as e:
            logging.error("내전 닫기 중 오류: %s", e, exc_info=True)
            await interaction.followup.send("내전 닫기 중 오류가 발생했습니다.", ephemeral=True)

    @discord.ui.button(label="취소", style=discord.ButtonStyle.gray)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("내전 닫기가 취소되었습니다.", ephemeral=True)

class ManageView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

        # 열기 버튼
        self.open_button = discord.ui.Button(
            label="열기",
            style=discord.ButtonStyle.green,
            custom_id="open_button"
        )
        self.open_button.callback = self.open_callback
        self.add_item(self.open_button)

        # 닫기 버튼
        self.close_button = discord.ui.Button(
            label="닫기",
            style=discord.ButtonStyle.red,
            custom_id="close_button"
        )
        self.close_button.callback = self.close_callback
        self.add_item(self.close_button)

        # 승리 버튼
        self.win_button = discord.ui.Button(
            label="승리",
            style=discord.ButtonStyle.blurple,
            custom_id="win_button"
        )
        self.win_button.callback = self.win_callback
        self.add_item(self.win_button)

        # 기록 버튼
        self.record_button = discord.ui.Button(
            label="기록",
            style=discord.ButtonStyle.primary,
            custom_id="record_button"
        )
        self.record_button.callback = self.record_callback
        self.add_item(self.record_button)

    async def record_callback(self, interaction: discord.Interaction):
     if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("이 버튼은 관리자만 사용할 수 있습니다.", ephemeral=True)
        return

     try:
        class RecordDownload(discord.ui.Modal, title="내전 기록 다운로드"):
            def __init__(self):
                super().__init__()
                self.date_input = discord.ui.TextInput(
                    label="날짜 입력 (YYYY-MM-DD)",
                    placeholder="기록을 다운로드할 날짜를 입력하세요",
                    required=True
                )
                self.add_item(self.date_input)

            async def on_submit(self, modal_interaction: discord.Interaction):
                try:
                    date_str = self.date_input.value.strip()
                    logging.debug(f"입력된 날짜: {date_str}")

                    # 저장된 파일 리스트 디버그 출력
                    logging.debug(f"저장된 파일 목록: {ongoing_war.saved_files}")

                    # 날짜 형식으로 매칭되는 파일 검색
                    matching_files = [
                        file for file in ongoing_war.saved_files
                        if date_str in os.path.basename(file).split("_")[1]  # 날짜 부분만 비교
                    ]

                    logging.debug(f"매칭된 파일: {matching_files}")

                    if not matching_files:
                        await modal_interaction.response.send_message(
                            "해당 날짜의 기록을 찾을 수 없습니다.", ephemeral=True
                        )
                        return

                    file_path = matching_files[0]  # 첫 번째 매칭 파일
                    await modal_interaction.response.send_message(
                        "기록 파일을 다운로드하세요:",
                        file=discord.File(file_path),
                        ephemeral=True
                    )
                except Exception as e:
                    logging.error("기록 다운로드 처리 중 오류 발생: %s", e, exc_info=True)
                    await modal_interaction.response.send_message(
                        "기록 다운로드 중 오류가 발생했습니다.", ephemeral=True
                    )

        await interaction.response.send_modal(RecordDownload())
     except Exception as e:
        logging.error("기록 버튼 처리 중 오류 발생: %s", e, exc_info=True)
        await interaction.response.send_message("기록 다운로드 중 오류가 발생했습니다.", ephemeral=True)

    async def open_callback(self, interaction: discord.Interaction):
     if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("이 버튼은 관리자만 사용할 수 있습니다.", ephemeral=True)
        return

     try:
        # 초기 응답 연장
        await interaction.response.defer(ephemeral=True)

        # 새 시트 생성
        new_sheet_name = sheets_manager.copy_sheet("경내(원본)")
        if new_sheet_name:
            ongoing_war.status = True
            ongoing_war.participants = []
            ongoing_war.current_sheet = new_sheet_name
            await interaction.followup.send(f"내전이 열렸습니다: {new_sheet_name}", ephemeral=True)
        else:
            await interaction.followup.send("내전을 열 수 없습니다. 오류가 발생했습니다.", ephemeral=True)
     except Exception as e:
        logging.error("내전 열기 중 오류: %s", e, exc_info=True)
        await interaction.followup.send("내전을 열기 중 오류가 발생했습니다.", ephemeral=True)


        # Start of Selection
    async def close_callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("이 버튼은 관리자만 사용할 수 있습니다.", ephemeral=True)
            return

        embed = discord.Embed(
            title="내전 닫기 확인",
            description="정말로 내전을 닫으시겠습니까?",
            color=discord.Color.red()
        )
        confirm_view = CloseConfirmView(interaction)
        await interaction.response.send_message(
            embed=embed,
            view=confirm_view,
            ephemeral=True
        )

        try:
            # 초기 응답 연장
            await interaction.response.defer(ephemeral=True)

            if ongoing_war.current_sheet:
                # 내전 기록 파일 생성
                file_name = f"내전기록_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.xlsx"
                file_path = os.path.join("records", file_name)
                sheets_manager.export_sheet_as_xlsx(ongoing_war.current_sheet, file_path)
                ongoing_war.saved_files.append(file_path)

                # 현재 시트 삭제
                sheets_manager.delete_sheet(ongoing_war.current_sheet)
                ongoing_war.reset()

                # 성공 메시지 전송
                await interaction.followup.send("내전이 성공적으로 닫혔습니다.", ephemeral=True)
            else:
                await interaction.followup.send("현재 활성화된 내전이 없습니다.", ephemeral=True)
        except Exception as e:
            logging.error("내전 닫기 중 오류: %s", e, exc_info=True)
            await interaction.followup.send("내전 닫기 중 오류가 발생했습니다.", ephemeral=True)


    async def win_callback(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("이 버튼은 관리자만 사용할 수 있습니다.", ephemeral=True)
            return

        try:
            # 초기 응답 연장
            await interaction.response.defer(ephemeral=True)

            if not ongoing_war.participants:
                await interaction.followup.send("참여자가 없습니다.", ephemeral=True)
                return

            # 승리 팀 선택 UI 생성
            options = [
                discord.SelectOption(label=participant["게임 닉네임"], value=participant["게임 닉네임"])
                for participant in ongoing_war.participants
            ]

            # 최소 옵션 개수 보장
            if len(options) < 10:
                dummy_options = [
                    discord.SelectOption(label=f"더미 옵션 {i+1}", value=f"dummy_{i+1}")
                    for i in range(10 - len(options))
                ]
                options.extend(dummy_options)

            class WinSelect(discord.ui.View):
                def __init__(self):
                    super().__init__()
                    self.select_menu = discord.ui.Select(
                        placeholder="승리팀을 최대 10명까지 선택하세요",
                        options=options,
                        custom_id="win_select",
                        max_values=10  # 최대 10명 선택 가능
                    )
                    self.select_menu.callback = self.select_winner
                    self.add_item(self.select_menu)

                async def select_winner(self, interaction: discord.Interaction):
                    try:
                        # Interaction 만료 방지
                        await interaction.response.defer(ephemeral=True)

                        selected_winners = [
                            value for value in self.select_menu.values if not value.startswith("dummy_")
                        ]
                        defeated_participants = [
                            participant["게임 닉네임"]
                            for participant in ongoing_war.participants
                            if participant["게임 닉네임"] not in selected_winners
                        ]

                        # 내전 기록 파일 생성
                        if ongoing_war.current_sheet:
                            file_name = f"내전기록_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.xlsx"
                            file_path = os.path.join("records", file_name)
                            sheets_manager.export_sheet_as_xlsx(ongoing_war.current_sheet, file_path)
                            ongoing_war.saved_files.append(file_path)

                            # 멤버 시트 업데이트
                            member_data = sheets_manager.get_values(sheet_name="MEMBER", range_notation="C:L")
                            
                            # 각 참가자에 대해 업데이트
                            for participant in ongoing_war.participants:
                                nickname = participant["게임 닉네임"]
                                
                                # 멤버 찾기 (태그 포함하여 정확히 매칭)
                                member_row = None
                                for idx, row in enumerate(member_data):
                                    if len(row) >= 2 and row[1].strip() == nickname:
                                        member_row = idx + 1
                                        break

                                if member_row:
                                    current_values = member_data[member_row - 1]
                                    
                                    # 현재 참여 횟수 가져오기 (J열)
                                    current_participation = int(current_values[7]) if len(current_values) > 7 and current_values[7].strip() else 0
                                    
                                    # 현재 승리 횟수 가져오기 (L열)
                                    current_wins = int(current_values[9]) if len(current_values) > 9 and current_values[9].strip() else 0
                                    
                                    # 참여 횟수 업데이트 (J열)
                                    sheets_manager.update_cell(
                                        sheet_name="MEMBER",
                                        start_column="J",
                                        start_row=member_row,
                                        values=[[current_participation + 1]]
                                    )
                                    
                                    # 승리자인 경우 승리 횟수 업데이트 (L열)
                                    if nickname in selected_winners:
                                        sheets_manager.update_cell(
                                            sheet_name="MEMBER",
                                            start_column="L",
                                            start_row=member_row,
                                            values=[[current_wins + 1]]
                                        )

                            # 시트 삭제
                            sheets_manager.delete_sheet(ongoing_war.current_sheet)
                            ongoing_war.reset()

                            # 결과 임베드 생성 및 채널 전송
                            embed = discord.Embed(
                                title="내전 결과",
                                description=f"진행된 날짜: {datetime.now().strftime('%m-%d')}\n"
                                          f"⭐ 승리: {', '.join(selected_winners)}\n"
                                          f"🧨 패배: {', '.join(defeated_participants)}",
                                color=discord.Color.green()
                            )

                            result_channel = interaction.guild.get_channel(1261185113446944869)  # 특정 채널 ID
                            if result_channel:
                                await result_channel.send(embed=embed)

                            await interaction.followup.send(
                                f"내전이 종료되었습니다! 승리팀: {', '.join(selected_winners)}", ephemeral=True
                            )
                        else:
                            await interaction.followup.send("활성화된 내전 시트가 없습니다.", ephemeral=True)

                    except Exception as e:
                        logging.error("승리 처리 중 오류 발생: %s", e, exc_info=True)
                        await interaction.followup.send("승리 처리 중 오류가 발생했습니다.", ephemeral=True)

            # 승리팀 선택 UI 전송
            await interaction.followup.send("승리팀을 선택하세요:", view=WinSelect(), ephemeral=True)
        except Exception as e:
            logging.error("승리 버튼 처리 중 오류 발생: %s", e, exc_info=True)
            await interaction.followup.send("승리 처리 중 오류가 발생했습니다.", ephemeral=True)

class WinSelectMenu(discord.ui.Select):
    def __init__(self, options):
        super().__init__(placeholder="승리팀을 선택하세요", min_values=1, max_values=1, options=options, ephemeral=True)

    async def callback(self, interaction: discord.Interaction):
        selected_team = self.values[0]
        try:
            await interaction.response.send_message(f"승리팀: {selected_team}로 기록되었습니다.", ephemeral=True)
            # 승리팀 기록 로직 추가
        except Exception as e:
            logging.error("승리팀 기록 중 오류: %s", e, exc_info=True)
            await interaction.response.send_message("승리팀 기록 중 오류가 발생했습니다.", ephemeral=True)

class WarCommand(app_commands.Group):
    def __init__(self):
        super().__init__(name="내전")

    @app_commands.command(name="관리", description="내전 관리 메시지를 전송합니다.")
    @app_commands.describe(채널="메시지를 전송할 채널을 선택하세요.")
    async def manage(self, interaction: discord.Interaction, 채널: discord.TextChannel):
        embed = discord.Embed(
            title="내전 참여 안내",
            description="내전에 참여하거나 취소하려면 아래 버튼을 사용하세요.",
            color=discord.Color.blue()
        )
        await 채널.send(embed=embed, view=WarView())
        await interaction.response.send_message(f"{채널.mention} 채널에 메시지가 전송되었습니다.", ephemeral=True)


async def setup(bot: commands.Bot):
    bot.add_view(WarView())
    bot.tree.add_command(WarCommand())