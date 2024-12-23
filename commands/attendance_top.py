from discord import Interaction, app_commands
import discord
import json
import os
from typing import Dict, Any

GUILD_ID = int(os.getenv("GUILD_ID"))
DATA_FILE = "attendance_data.json"

# 데이터 파일 로드
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        attendance = json.load(f)
else:
    attendance = {}

class Paginator(discord.ui.View):
    """페이지네이션을 위한 Discord UI View"""
    def __init__(self, embeds):
        super().__init__(timeout=None)
        self.embeds = embeds
        self.current_page = 0

        # 버튼 생성
        self.prev_button = discord.ui.Button(label="⬅️ 이전", style=discord.ButtonStyle.primary)
        self.page_label = discord.ui.Button(label=f"{self.current_page + 1}/{len(self.embeds)}", style=discord.ButtonStyle.secondary, disabled=True)
        self.next_button = discord.ui.Button(label="➡️ 다음", style=discord.ButtonStyle.primary)

        # 콜백 연결
        self.prev_button.callback = self.prev_page
        self.next_button.callback = self.next_page

        # 버튼 추가
        self.add_item(self.prev_button)
        self.add_item(self.page_label)
        self.add_item(self.next_button)

        self.update_buttons_state()

    def update_buttons_state(self):
        """현재 페이지에 따라 버튼 상태 업데이트"""
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == len(self.embeds) - 1
        self.page_label.label = f"{self.current_page + 1}/{len(self.embeds)}"

    async def update_message(self, interaction):
        """메시지를 업데이트"""
        self.update_buttons_state()
        await interaction.response.edit_message(embed=self.embeds[self.current_page], view=self)

    async def prev_page(self, interaction: discord.Interaction):
        """이전 페이지로 이동"""
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_message(interaction)
        else:
            await interaction.response.send_message("현재 페이지가 첫 번째 페이지입니다.", ephemeral=True)

    async def next_page(self, interaction: discord.Interaction):
        """다음 페이지로 이동"""
        if self.current_page < len(self.embeds) - 1:
            self.current_page += 1
            await self.update_message(interaction)
        else:
            await interaction.response.send_message("현재 페이지가 마지막 페이지입니다.", ephemeral=True)

def load_attendance_data() -> Dict[str, Any]:
    """출석 데이터를 로드하는 함수"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("JSON 파일 읽기 오류. 빈 데이터로 초기화합니다.")
            return {}
    return {}

@app_commands.command(name="순위", description="출석 순위를 확인합니다.")
@app_commands.guilds(discord.Object(id=GUILD_ID))  # 특정 서버로 제한
async def 순위(interaction: Interaction):
    # 응답 지연 처리
    await interaction.response.defer()

    # 데이터 로드
    attendance = load_attendance_data()

    if not attendance:
        await interaction.followup.send("아직 출석 기록이 없습니다!", ephemeral=False)
        return

    try:
        # 출석 데이터를 정렬
        sorted_attendance = sorted(
            attendance.items(),
            key=lambda x: x[1].get("count", 0) if isinstance(x[1], dict) else 0,
            reverse=True
        )

        # 임베드 생성
        embeds = []
        embed = discord.Embed(
            title="📊 출석 순위",
            description="출석 횟수에 따른 순위입니다.",
            color=discord.Color.blue()
        )

        for rank, (user_id, data) in enumerate(sorted_attendance, start=1):
            try:
                member = await interaction.guild.fetch_member(int(user_id))
                if member:
                    count = data.get("count", 0) if isinstance(data, dict) else 0
                    rank_display = "👑 1위" if rank == 1 else f"{rank}위"
                    embed.add_field(name=rank_display, value=f"{member.display_name} - {count}회", inline=False)

                    # 10개 항목마다 새로운 임베드 생성
                    if rank % 10 == 0:
                        embeds.append(embed)
                        embed = discord.Embed(
                            title="📊 출석 순위",
                            description="출석 횟수에 따른 순위입니다.",
                            color=discord.Color.blue()
                        )
            except discord.NotFound:
                continue
            except discord.HTTPException:
                continue

        if len(embed.fields) > 0:
            embeds.append(embed)

        if not embeds:
            await interaction.followup.send("표시할 순위가 없습니다.", ephemeral=False)
            return

        # 페이지네이션 처리
        view = Paginator(embeds)
        if len(embeds) == 1:
            await interaction.followup.send(embed=embeds[0], ephemeral=False)
        else:
            await interaction.followup.send(embed=embeds[0], view=view, ephemeral=False)

    except Exception as e:
        await interaction.followup.send(f"순위를 가져오는 중 오류가 발생했습니다: {e}", ephemeral=False)
