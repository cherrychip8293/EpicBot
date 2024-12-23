from datetime import datetime
from discord import app_commands, Interaction, Embed, TextChannel
import discord
import pytz
from event.GoogleSheetsManager import GoogleSheetsManager

# Google Sheets 설정
SERVICE_ACCOUNT_FILE = 'resources/service_account.json'
SPREADSHEET_ID = '1AYSWQwLOA-EvMJzJ7ros27OEzrTd2hERlI2WJX32RBE'
LOG_CHANNEL_ID = 1320605395676299305  # 로그를 전송할 Discord 채널 ID

seoul_tz = pytz.timezone("Asia/Seoul")
current_time = datetime.now(seoul_tz)

# Google Sheets 매니저 초기화
sheets_manager = GoogleSheetsManager(SERVICE_ACCOUNT_FILE, SPREADSHEET_ID)


class InfoChangeModal(discord.ui.Modal, title="정보 변경"):
    """
    정보 변경을 위한 Modal
    """
    def __init__(self):
        super().__init__()

        self.old_nickname = discord.ui.TextInput(
            label="이전 닉네임",
            placeholder="태그 포함된 이전 닉네임을 입력하세요",
            required=True
        )
        self.new_nickname = discord.ui.TextInput(
            label="변경된 닉네임",
            placeholder="태그 포함된 변경 후 닉네임을 입력하세요",
            required=True
        )
        self.new_tier = discord.ui.TextInput(
            label="변경된 티어",
            placeholder="변경 후 티어를 입력하세요",
            required=True
        )
        self.reason = discord.ui.TextInput(
            label="변경 사유",
            placeholder="변경 사유를 입력하세요",
            required=True,
            style=discord.TextStyle.long
        )

        self.add_item(self.old_nickname)
        self.add_item(self.new_nickname)
        self.add_item(self.new_tier)
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction):
        """
        Modal 제출 시 처리 로직
        """
        try:
            # 초기 응답
            await interaction.response.defer(ephemeral=True)

            old_nickname = self.old_nickname.value.strip()
            new_nickname = self.new_nickname.value.strip()
            new_tier = self.new_tier.value.strip()
            reason = self.reason.value.strip()

            # MEMBER 시트에서 이전 닉네임 검색
            member_data = sheets_manager.get_values(sheet_name="MEMBER", range_notation="A:Z")
            target_row = None

            for row_idx, row in enumerate(member_data):
                if len(row) >= 4 and row[3].strip() == old_nickname:
                    target_row = row_idx + 1  # Google Sheets는 1부터 시작
                    break

            if not target_row:
                await interaction.followup.send("해당 닉네임을 가진 멤버를 찾을 수 없습니다.", ephemeral=True)
                return

            # D열에 새로운 닉네임, E열에 새로운 티어 입력
            sheets_manager.update_cell(sheet_name="MEMBER", start_column="D", start_row=target_row, values=[[new_nickname]])
            sheets_manager.update_cell(sheet_name="MEMBER", start_column="E", start_row=target_row, values=[[new_tier]])

            # 성공 메시지
            await interaction.followup.send(
                f"'{old_nickname}' 닉네임이 '{new_nickname}'(으)로, 티어가 '{new_tier}'(으)로 성공적으로 변경되었습니다.",
                ephemeral=True
            )

            # 로그 채널로 변경 사유 전송
            guild = interaction.guild
            if guild:
                log_channel = guild.get_channel(LOG_CHANNEL_ID)
                if isinstance(log_channel, TextChannel):
                    embed = Embed(
                        title="정보 변경 로그",
                        description=f"**변경자**: {interaction.user.mention}",
                        color=0x00FF00  # 녹색
                    )
                    embed.add_field(name="이전 닉네임", value=f"`{old_nickname}`", inline=False)
                    embed.add_field(name="변경된 닉네임", value=f"`{new_nickname}`", inline=False)
                    embed.add_field(name="변경된 티어", value=f"`{new_tier}`", inline=False)
                    embed.add_field(name="사유", value=f"`{reason}`", inline=False)
                    embed.set_footer(text=f"요청자: {interaction.user.display_name}\n {current_time.strftime('%Y-%m-%d %H:%M:%S')}")

                    await log_channel.send(embed=embed)

        except Exception as e:
            await interaction.followup.send(f"정보 변경 중 오류 발생: {e}", ephemeral=True)


class InfoChangeView(discord.ui.View):
    """
    정보 변경을 위한 버튼 포함 View
    """
    def __init__(self):
        super().__init__(timeout=None)  # View가 영구적으로 유지되도록 설정

        self.change_button = discord.ui.Button(
            label="정보 변경",
            style=discord.ButtonStyle.green,
            custom_id="info_change_button"
        )
        self.change_button.callback = self.change_info
        self.add_item(self.change_button)

    async def change_info(self, interaction: discord.Interaction):
        """
        버튼 클릭 시 Modal 표시
        """
        modal = InfoChangeModal()
        await interaction.response.send_modal(modal)


@app_commands.command(name="정보변경메시지", description="정보 변경을 위한 메시지를 특정 채널에 전송합니다.")
@app_commands.describe(채널="메시지를 보낼 채널을 선택하세요")
async def 정보변경메시지(interaction: discord.Interaction, 채널: TextChannel):
    if not 채널:
        await interaction.response.send_message("메시지를 보낼 채널을 선택하세요.", ephemeral=True)
        return

    embed = Embed(
        title="정보 변경 안내",
        description="정보를 변경하려면 아래 버튼을 클릭하세요.\n**닉네임 또는 탑 레이팅 갱신시 사용해주세요.**",
        color=discord.Color.blue()
    )

    await 채널.send(embed=embed, view=InfoChangeView())
    await interaction.response.send_message(f"{채널.mention} 채널에 정보 변경 메시지를 전송했습니다.", ephemeral=True)


async def setup(bot: discord.Client):
    bot.add_view(InfoChangeView())  # View 등록
    bot.tree.add_command(정보변경메시지)