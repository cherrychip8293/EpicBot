import logging
from discord import app_commands
import discord
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
    """
    봇이 재시작될 때 기존의 내전 상태를 복구합니다.
    """
    try:
        sheet_names = sheets_manager.get_sheet_names()
        if not sheet_names:
            logging.error("시트 이름 목록을 가져오지 못했습니다. 스프레드시트 API를 확인하세요.")
            return  # 함수 종료

        logging.debug(f"가져온 시트 이름 목록: {sheet_names}")

        today_date = datetime.now().strftime('%Y-%m-%d')
        active_sheet_name = f"내전-{today_date}"

        if active_sheet_name in sheet_names:
            ongoing_war.status = True
            ongoing_war.current_sheet = active_sheet_name
            logging.info(f"내전 활성화 상태 복구: {active_sheet_name}")
        else:
            logging.info("내전 활성화 상태가 발견되지 않았습니다.")
    except Exception as e:
        logging.error(f"내전 상태 복구 중 오류 발생: {e}", exc_info=True)


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
            # 초기 응답 연장
            await interaction.response.defer(ephemeral=True)

            nickname = self.nickname.value.strip()
            line = self.line.value.strip()

            # 멤버 시트에서 닉네임과 태그를 완전히 매칭
            member_data = sheets_manager.get_values(sheet_name="MEMBER", range_notation="C:D")
            member_row = next(
                (
                    row for row in member_data
                    if len(row) >= 2 and row[1].strip() == nickname
                ),
                None
            )

            if not member_row:
                await interaction.followup.send("닉네임#태그를 찾을 수 없습니다.", ephemeral=True)
                return

            # 멤버 정보
            member_number = member_row[0].lstrip("'").strip()  # 순번
            full_nickname = member_row[1].strip()  # 닉네임 (태그 포함)

            # 내전 시트에 데이터 추가
            if ongoing_war.current_sheet:
                start_row = 5 + len(ongoing_war.participants)  # 시작 행
                sheets_manager.update_cell(
                    sheet_name=ongoing_war.current_sheet,
                    start_column="W",  # 순번 열
                    start_row=start_row,
                    values=[[member_number, full_nickname, line]]  # 닉네임에 태그 포함
                )
            else:
                await interaction.followup.send("내전 시트가 활성화되지 않았습니다.", ephemeral=True)
                return

            # 참여자 목록에 추가
            ongoing_war.participants.append({
                "디스코드 닉네임": interaction.user.name,
                "게임 닉네임": full_nickname,  # 태그 포함된 닉네임 저장
                "라인": line
            })

            await interaction.followup.send(f"{interaction.user.mention} 님의 참여가 기록되었습니다.", ephemeral=True)
        except Exception as e:
            logging.error("참여 기록 중 오류 발생: %s", e, exc_info=True)
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


    async def close_callback(self, interaction: discord.Interaction):
     if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("이 버튼은 관리자만 사용할 수 있습니다.", ephemeral=True)
        return

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

async def setup(bot: discord.Client):
    bot.add_view(WarView())
    bot.tree.add_command(WarCommand())