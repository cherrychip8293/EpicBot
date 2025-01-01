import json
from datetime import datetime
import discord
from discord.ext import commands
from discord import app_commands
import logging
import os
from event.GoogleSheetsManager import GoogleSheetsManager

# Google Sheets 설정
SERVICE_ACCOUNT_FILE = "resources/service_account.json"
SPREADSHEET_ID = "1AYSWQwLOA-EvMJzJ7ros27OEzrTd2hERlI2WJX32RBE"
sheets_manager = GoogleSheetsManager(SERVICE_ACCOUNT_FILE, SPREADSHEET_ID)

class AttendanceCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.attendance_data = {}
        self.ATTENDANCE_CHANNEL_ID = 1321697990003654732
        self.GUILD_ID = int(os.getenv("GUILD_ID"))  # 환경 변수에서 서버 ID 가져오기
        
        # Role settings
        self.ROLE_THRESHOLDS = {
            1321704148244365405: 50,  # 50회 출석 역할
            1256291165238726707: 100, # 100회 출석 역할
            1256291250391482569: 300, # 300회 출석 역할
        }
        
        self.ROLE_INCREMENT_VALUES = {
            1321704148244365405: 10,
            1256291165238726707: 10,
            1256291250391482569: 20,
        }
        
        # Google Sheets setup
        SERVICE_ACCOUNT_FILE = "resources/service_account.json"
        SPREADSHEET_ID = "1AYSWQwLOA-EvMJzJ7ros27OEzrTd2hERlI2WJX32RBE"
        self.sheets_manager = GoogleSheetsManager(SERVICE_ACCOUNT_FILE, SPREADSHEET_ID)

    async def cog_load(self):
        try:
            with open("attendance_data.json", "r", encoding="utf-8") as f:
                self.attendance_data = json.load(f)
            logging.info("출석 데이터 로드 완료")
        except FileNotFoundError:
            self.attendance_data = {}
            logging.info("새로운 출석 데이터 파일 생성")

    def save_attendance(self):
        with open("attendance_data.json", "w", encoding="utf-8") as f:
            json.dump(self.attendance_data, f, indent=4)
            logging.info("출석 데이터 저장 완료")

    # 일반 명령어 (prefix commands)
    @commands.command(name="출석", aliases=["출첵"])
    async def attendance_text(self, ctx):
        if ctx.channel.id != self.ATTENDANCE_CHANNEL_ID:
            await ctx.send("이 채널에서는 출석체크를 할 수 없습니다!")
            return
        await self._handle_attendance(ctx, ctx.author)

    # 슬래시 명령어
    @app_commands.command(
        name="출석",
        description="오늘의 출석을 체크합니다."
    )
    @app_commands.guilds(1321697990003654729)  # 여기에 서버 ID를 직접 넣어도 됩니다
    async def attendance_app_command(self, interaction: discord.Interaction):
        if interaction.channel_id != self.ATTENDANCE_CHANNEL_ID:
            await interaction.response.send_message("이 채널에서는 출석체크를 할 수 없습니다!", ephemeral=True)
            return
        await self._handle_attendance(interaction, interaction.user)

    async def _handle_attendance(self, ctx, user):
        user_id = str(user.id)
        today = str(datetime.now().date())

        # 출석 데이터 확인 및 업데이트
        if user_id not in self.attendance_data:
            self.attendance_data[user_id] = {"last_date": None, "count": 0}

        user_data = self.attendance_data[user_id]

        if user_data["last_date"] == today:
            message = f"{user.mention}, 오늘 이미 출석체크를 했습니다! 총 출석 횟수: {user_data['count']}회"
        else:
            user_data["last_date"] = today
            user_data["count"] += 1
            self.save_attendance()
            message = f"{user.mention}, 출석체크 완료! 총 출석 횟수: {user_data['count']}회"

        try:
            # 즉시 응답을 전송
            if isinstance(ctx, discord.Interaction):
                await ctx.response.send_message(message, ephemeral=True)
            else:
                await ctx.send(message)

            # 역할 부여 작업은 비동기로 처리
            await self.check_and_award_role(ctx, user, user_data["count"])
        except Exception as e:
            logging.error(f"응답 처리 중 오류 발생: {e}", exc_info=True)

    async def check_and_award_role(self, interaction_or_message, user: discord.Member, user_count: int):
        """
        출석 횟수에 따라 역할 지급 및 Google Sheets 업데이트
        """
        guild = user.guild
        if not guild:
            return

        awarded_role = None

        for role_id, required_count in self.ROLE_THRESHOLDS.items():
            if user_count >= required_count:
                role = guild.get_role(role_id)
                if role and role not in user.roles:
                    await user.add_roles(role)
                    awarded_role = role_id
                    if isinstance(interaction_or_message, discord.Interaction):
                        await interaction_or_message.channel.send(
                            f"{user.mention}, 축하합니다! 출석 {required_count}회를 달성하여 역할 `{role.name}`을 지급받았습니다! 🎉"
                        )
                    else:
                        await interaction_or_message.channel.send(
                            f"{user.mention}, 축하합니다! 출석 {required_count}회를 달성하여 역할 `{role.name}`을 지급받았습니다! 🎉"
                        )
                    logging.info(f"[역할 지급] 대상: {user.display_name}, 지급된 역할: {role.name}, 출석 횟수: {user_count}")
                    break

        # Google Sheets 업데이트
        try:
            raw_nickname = user.display_name
            nickname = sheets_manager.clean_nickname(raw_nickname)

            if not nickname:
                logging.info(f"[닉네임 비어있음] 원본 닉네임: {raw_nickname}")
                return

            member_data = sheets_manager.get_values(sheet_name="MEMBER", range_notation="D:D")
            member_row = next(
                (
                    row for row in member_data
                    if len(row) >= 1 and row[0].split('#')[0].strip() == nickname
                ),
                None
            )

            if member_row:
                row_index = member_data.index(member_row) + 1
                increment_value = self.ROLE_INCREMENT_VALUES.get(awarded_role, 0)
                if increment_value > 0:
                    current_values = sheets_manager.get_values(sheet_name="MEMBER", range_notation=f"N{row_index}:N{row_index}")
                    current_value = int(current_values[0][0]) if current_values and current_values[0] else 0
                    updated_value = current_value + increment_value
                    sheets_manager.update_cell(
                        sheet_name="MEMBER",
                        start_column="N",
                        start_row=row_index,
                        values=[[updated_value]]
                    )
                    logging.info(f"[출석] 대상: {nickname}, 이전 값: {current_value}, 추가 값: {increment_value}, 갱신된 값: {updated_value}")
            else:
                logging.info(f"[출석] Google Sheets에서 닉네임 '{nickname}'을(를) 찾을 수 없습니다.")
        except Exception as e:
            logging.error(f"[오류 발생] Google Sheets 업데이트 중 오류: {e}")

async def setup(bot):
    try:
        await bot.add_cog(AttendanceCommands(bot))
        logging.info('AttendanceCommands가 성공적으로 로드되었습니다.')
    except Exception as e:
        logging.error(f'AttendanceCommands 로드 중 오류 발생: {e}')