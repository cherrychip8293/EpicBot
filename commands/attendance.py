import json
from datetime import datetime
from discord import app_commands, Interaction
import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
from event.GoogleSheetsManager import GoogleSheetsManager

# Google Sheets 설정
SERVICE_ACCOUNT_FILE = "resources/service_account.json"
SPREADSHEET_ID = "1AYSWQwLOA-EvMJzJ7ros27OEzrTd2hERlI2WJX32RBE"
sheets_manager = GoogleSheetsManager(SERVICE_ACCOUNT_FILE, SPREADSHEET_ID)

load_dotenv()
DATA_FILE = "attendance_data.json"
GUILD_ID = int(os.getenv("GUILD_ID"))
ATTENDANCE_CHANNEL_ID = 1255576193990787113  # 출석 가능 채널 ID

# 역할 지급 조건
ROLE_THRESHOLDS = {
    1256291091838402611: 50,
    1256291165238726707: 100,
    1256291250391482569: 300,
}

# 역할별 추가 값 설정
ROLE_INCREMENT_VALUES = {
    1256291091838402611: 10,
    1256291165238726707: 10,
    1256291250391482569: 20,
}

# 데이터 파일 로드
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        attendance = json.load(f)
else:
    attendance = {}

# 데이터 저장 함수
def save_attendance():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(attendance, f, indent=4)

async def check_and_award_role(interaction_or_message, user: discord.Member, user_count: int):
    """
    출석 횟수에 따라 역할 지급 및 Google Sheets 업데이트
    """
    guild = user.guild
    if not guild:
        return

    awarded_role = None

    for role_id, required_count in ROLE_THRESHOLDS.items():
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
                print(f"Role {role.name} ({role_id}) awarded to {user.display_name}.")
                break

    # Google Sheets 업데이트
    try:
        nickname = user.display_name
        member_data = sheets_manager.get_row_by_value(
            sheet_name="MEMBER",
            column_name="D",
            value=nickname
        )

        if member_data:
            row_index = member_data['row_index']
            increment_value = ROLE_INCREMENT_VALUES.get(awarded_role, 0)
            if increment_value > 0:
                current_value = sheets_manager.get_cell_value(
                    sheet_name="MEMBER",
                    row=row_index,
                    column_name="N"
                )
                updated_value = (int(current_value) if current_value.isdigit() else 0) + increment_value
                sheets_manager.update_cell(
                    sheet_name="MEMBER",
                    row=row_index,
                    column_name="N",
                    value=updated_value
                )
                print(f"Updated Google Sheets: Row {row_index}, Column N. Old Value: {current_value}, Increment: {increment_value}, New Value: {updated_value}.")
        else:
            print(f"디스코드 닉네임 {nickname}에 해당하는 데이터가 Google Sheets에서 발견되지 않았습니다.")
    except Exception as e:
        print(f"Google Sheets 업데이트 중 오류 발생: {e}")

# 슬래시 커맨드
@app_commands.command(name="출석", description="오늘의 출석을 체크합니다.")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def 출석(interaction: Interaction):
    if interaction.channel.id != ATTENDANCE_CHANNEL_ID:
        await interaction.response.send_message("이 채널에서는 출석체크를 할 수 없습니다!", ephemeral=True)
        return

    user = interaction.user
    user_id = str(user.id)
    today = str(datetime.now().date())

    if user_id not in attendance:
        attendance[user_id] = {"last_date": None, "count": 0}

    user_data = attendance[user_id]

    if user_data["last_date"] == today:
        await interaction.response.send_message(
            f"{user.mention}, 오늘 이미 출석체크를 했습니다! 총 출석 횟수: {user_data['count']}회"
        )
    else:
        user_data["last_date"] = today
        user_data["count"] += 1
        save_attendance()

        await interaction.response.send_message(
            f"{user.mention}, 출석체크 완료! 총 출석 횟수: {user_data['count']}회"
        )

        await check_and_award_role(interaction, user, user_data["count"])

# 기존 슬래시 명령어는 유지
async def setup(bot):
    bot.tree.add_command(출석)