from discord import Guild, Member
import json
import os

# 데이터 파일
DATA_FILE = "attendance_data.json"

def load_attendance_data():
    """출석 데이터를 로드하는 함수"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_attendance_data(data):
    """출석 데이터를 저장하는 함수"""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

async def check_and_award_role(guild: Guild, member: Member, role_threshold: dict):
    """
    특정 출석 횟수 도달 시 역할 지급
    :param guild: Discord Guild 객체
    :param member: Discord Member 객체
    :param role_threshold: {role_id: required_count} 형식의 역할 지급 조건
    """
    attendance = load_attendance_data()
    user_id = str(member.id)

    if user_id in attendance:
        user_count = attendance[user_id].get("count", 0)

        for role_id, required_count in role_threshold.items():
            if user_count >= required_count:
                role = guild.get_role(role_id)
                if role and role not in member.roles:
                    await member.add_roles(role)
                    print(f"역할 '{role.name}'이(가) {member.display_name}에게 지급되었습니다.")
