import logging
import discord
from discord import app_commands
from discord.ext import commands
from event.GoogleSheetsManager import GoogleSheetsManager
import os

logging.basicConfig(level=logging.DEBUG, format="[%(asctime)s] [%(levelname)s] %(message)s")

# Google Sheets 설정
SERVICE_ACCOUNT_FILE = 'resources/service_account.json'
SPREADSHEET_ID = '1AYSWQwLOA-EvMJzJ7ros27OEzrTd2hERlI2WJX32RBE'
LOG_CHANNEL_ID = 1320646623969280042

# Google Sheets 매니저 초기화
sheets_manager = GoogleSheetsManager(SERVICE_ACCOUNT_FILE, SPREADSHEET_ID)

class ProductNumberInput(discord.ui.Modal, title='상품 구매'):
    def __init__(self, shop_view):
        super().__init__()
        self.shop_view = shop_view

        self.product_number = discord.ui.TextInput(
            label='상품 번호',
            placeholder='구매하실 상품의 번호를 입력하세요',
            required=True,
            min_length=1,
            max_length=3
        )
        self.add_item(self.product_number)

    async def on_submit(self, interaction: discord.Interaction):
        await self.shop_view.process_purchase(interaction, self.product_number.value)

class ProductInfoButton(discord.ui.Button):
    def __init__(self, shop_view):
        super().__init__(
            label="🛒상품 정보",
            style=discord.ButtonStyle.primary,
            custom_id="shop_product_info_button"  # 고유한 custom_id 추가
        )
        self.shop_view = shop_view

    async def callback(self, interaction: discord.Interaction):
        """상품 정보를 표시"""
        new_view = ProductInfoView(self.shop_view.shop_data)
        await interaction.response.send_message(
            embed=await new_view.generate_embed(),
            view=new_view,
            ephemeral=True
        )

class MileageButton(discord.ui.Button):
    def __init__(self, shop_view):
        super().__init__(
            label="⭐마일리지 보기",
            style=discord.ButtonStyle.secondary,
            custom_id="show_mileage_button"
        )
        self.shop_view = shop_view

    async def callback(self, interaction: discord.Interaction):
        """마일리지 확인 버튼 콜백"""
        try:
            logging.debug("마일리지 보기 요청 - 사용자: %s", interaction.user.display_name)
            await interaction.response.defer(ephemeral=True)
            
            # 디스코드 닉네임에서 유효한 단어만 추출
            def extract_valid_nickname(display_name):
                parts = display_name.split()
                valid_parts = []
                for part in parts:
                    # 숫자가 포함된 단어는 제외
                    if any(char.isdigit() for char in part):
                        continue
                    # 성별 표시 단어 '남', '여' 제외
                    if part in ['남', '여']:
                        continue
                    # 롤 티어 스펠링 약자 제외
                    if part in ['M', 'U', 'P', 'D', 'G', 'E', 'GM']:
                        continue
                    # 유효한 단어만 추가
                    valid_parts.append(part)
                return ' '.join(valid_parts).strip()

            # 닉네임 추출
            discord_nickname = extract_valid_nickname(interaction.user.display_name)
            logging.debug("추출된 닉네임: '%s'", discord_nickname)

            # Google Sheets 데이터 가져오기
            member_data = sheets_manager.get_values(sheet_name="MEMBER", range_notation="D2:F1000")
            logging.debug("Google Sheets 데이터 조회 결과: %s", member_data)
            
            if not member_data:
                await interaction.followup.send("데이터를 불러오는데 실패했습니다.", ephemeral=True)
                logging.error("마일리지 데이터 조회 실패")
                return

            # 닉네임 비교
            for row in member_data:
                if len(row) >= 3:
                    sheet_nickname = row[0].split('#')[0].strip()
                    logging.debug("비교: 디스코드 닉네임 '%s' vs 시트 닉네임 '%s'", discord_nickname, sheet_nickname)
                    
                    if sheet_nickname == discord_nickname:
                        current_mileage = row[2].strip()
                        logging.debug("마일리지 정보 찾음 - 현재 마일리지: %s", current_mileage)
                        await interaction.followup.send(
                            f"{interaction.user.mention}님의 현재 마일리지는 `{current_mileage}`입니다.",
                            ephemeral=True
                        )
                        return

            # 닉네임이 일치하지 않는 경우
            logging.warning("닉네임 '%s'에 대한 마일리지 정보 없음", discord_nickname)
            await interaction.followup.send(
                f"{interaction.user.mention}님의 마일리지 정보를 찾을 수 없습니다.",
                ephemeral=True
            )

        except Exception as e:
            logging.error("마일리지 보기 중 오류 발생: %s", e, exc_info=True)
            try:
                await interaction.followup.send(
                    f"마일리지 조회 중 오류가 발생했습니다: {str(e)}",
                    ephemeral=True
                )
            except discord.errors.InteractionResponded:
                logging.warning("마일리지 보기 - 이미 응답된 상호작용")

class ProductInfoView(discord.ui.View):
    def __init__(self, shop_data):
        super().__init__(timeout=None)
        self.shop_data = shop_data
        self.page = 0
        self.items_per_page = 5
        self.max_pages = max((len(self.shop_data) - 1) // self.items_per_page + 1, 1)

    async def generate_embed(self):
        embed = discord.Embed(title="상품 정보", color=discord.Color.blue())

        start_idx = self.page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.shop_data))
        page_items = self.shop_data[start_idx:end_idx]

        if not page_items:
            embed.description = "상품 정보가 없습니다."
        else:
            for row in page_items:
                embed.add_field(
                    name=f"상품 번호: {row[0]}",
                    value=f"상품 이름: {row[1]}\n구매 비용: {row[2]} 마일리지",
                    inline=False
                )

        embed.set_footer(text=f"페이지 {self.page + 1}/{self.max_pages}")
        return embed

    @discord.ui.button(label="⬅️ 이전", style=discord.ButtonStyle.secondary, custom_id="product_info_prev")
    async def prev_page_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page > 0:
            self.page -= 1
            await interaction.response.edit_message(embed=await self.generate_embed())
        else:
            await interaction.response.defer()

    @discord.ui.button(label="➡️ 다음", style=discord.ButtonStyle.secondary, custom_id="product_info_next")
    async def next_page_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.page < self.max_pages - 1:
            self.page += 1
            await interaction.response.edit_message(embed=await self.generate_embed())
        else:
            await interaction.response.defer()

class PersistentShopView(discord.ui.View):
    def __init__(self, shop_data):
        super().__init__(timeout=None)

        # 중복 제거하고 유효한 데이터만 필터링
        self.shop_data = []
        seen_products = set()

        for row in shop_data:
            if (len(row) >= 3 and 
                row[0].isdigit() and 
                row[0].strip() not in seen_products):
                self.shop_data.append(row)
                seen_products.add(row[0].strip())

        self.page = 0
        self.items_per_page = 5
        self.max_pages = max((len(self.shop_data) - 1) // self.items_per_page + 1, 1)

        # 버튼 추가
        self.add_item(ProductInfoButton(self))
        self.add_item(MileageButton(self))

    async def generate_embed(self):
        """현재 페이지의 상품 정보를 Embed로 생성"""
        embed = discord.Embed(title="상품 정보", color=discord.Color.blue())

        # 페이지 계산
        start_idx = self.page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.shop_data))

        # 현재 페이지의 상품 가져오기
        page_items = self.shop_data[start_idx:end_idx]

        if not page_items:
            embed.description = "상품 정보가 없습니다."
        else:
            for row in page_items:
                embed.add_field(
                    name=f"상품 번호: {row[0]}",
                    value=f"상품 이름: {row[1]}\n구매 비용: {row[2]} 마일리지",
                    inline=False
                )

        embed.set_footer(text=f"페이지 {self.page + 1}/{self.max_pages}")
        return embed

    async def show_mileage(self, interaction: discord.Interaction):
        """사용자의 마일리지 정보를 표시"""
        try:
            logging.debug("마일리지 보기 요청 - 사용자: %s", interaction.user.display_name)
            await interaction.response.defer(ephemeral=True)

            discord_nickname = interaction.user.display_name
            member_data = sheets_manager.get_values(sheet_name="MEMBER", range_notation="D2:F1000")

            for row in member_data:
                if len(row) >= 3 and row[0].strip() == discord_nickname:
                    current_mileage = row[2].strip()
                    await interaction.followup.send(
                        f"{interaction.user.mention}님의 현재 마일리지는 `{current_mileage}`입니다.",
                        ephemeral=True
                    )
                    return

            await interaction.followup.send(
                f"{interaction.user.mention}님의 마일리지 정보를 찾을 수 없습니다.",
                ephemeral=True
            )
        except Exception as e:
            logging.error("마일리지 보기 중 오류 발생: %s", e, exc_info=True)
            await interaction.followup.send("마일리지 정보를 불러오는 중 오류가 발생했습니다.", ephemeral=True)

    async def show_product_info(self, interaction: discord.Interaction):
        """상품 정보를 표시하고 버튼을 추가"""
        await interaction.response.send_message(embed=await self.generate_embed(), view=self, ephemeral=True)

    async def process_purchase(self, interaction: discord.Interaction, product_number: str):
        """상품 구매 처리"""
        try:
            await interaction.response.defer(ephemeral=True)
            discord_nickname = interaction.user.display_name
            member_data = sheets_manager.get_values(sheet_name="MEMBER", range_notation="D2:P1000")
            shop_data = sheets_manager.get_values(sheet_name="상점", range_notation="J2:L100")

            product = next((row for row in shop_data if len(row) >= 3 and row[0].strip() == product_number.strip()), None)
            if not product:
                await interaction.followup.send("해당 상품 번호를 찾을 수 없습니다.", ephemeral=True)
                return

            user_row = None
            current_balance = 0
            for idx, row in enumerate(member_data):
                if len(row) >= 3 and row[0].strip() == discord_nickname:
                    user_row = idx + 2
                    current_balance = int(row[2].strip())
                    break

            if user_row is None:
                await interaction.followup.send("회원 정보를 찾을 수 없습니다.", ephemeral=True)
                return

            product_cost = int(product[2].strip())
            if current_balance < product_cost:
                await interaction.followup.send(
                    f"마일리지가 부족합니다. (현재 잔액: `{current_balance}`, 필요 마일리지: `{product_cost}`)",
                    ephemeral=True
                )
                return

            new_balance = current_balance - product_cost
            sheets_manager.update_cell(
                sheet_name="MEMBER",
                start_column="F",
                start_row=user_row,
                values=[[str(new_balance)]]
            )

            await interaction.followup.send(
                f"'{product[1]}' 상품을 구매하였습니다! 남은 마일리지: `{new_balance}`.",
                ephemeral=True
            )
        except Exception as e:
            logging.error("상품 구매 처리 중 오류 발생: %s", e, exc_info=True)
            await interaction.followup.send("상품 구매 처리 중 오류가 발생했습니다.", ephemeral=True)

class ShopCommands(commands.Cog):
    """상점 관련 명령어 Cog"""
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="상점알림", description="지정된 채널에 상점 알림을 보냅니다.")
    @app_commands.describe(채널="알림을 보낼 채널을 선택하세요")
    async def shop_notification(self, interaction: discord.Interaction, 채널: discord.TextChannel):
        try:
            await interaction.response.defer(ephemeral=True)

            permissions = 채널.permissions_for(interaction.guild.me)
            if not permissions.send_messages or not permissions.embed_links:
                await interaction.followup.send("해당 채널에 메시지를 보낼 권한이 없습니다. 봇의 권한을 확인해주세요.", ephemeral=True)
                return

            shop_data = sheets_manager.get_values(sheet_name="상점", range_notation="J2:L100")
            if not shop_data:
                await interaction.followup.send("상품 정보가 없습니다.", ephemeral=True)
                return

            embed = discord.Embed(
                title="상점 안내",
                description="아래 버튼을 클릭하여 상품 정보를 확인하거나 본인 마일리지 정보를 확인하세요!",
                color=discord.Color.green()
            )
            view = PersistentShopView(shop_data)
            await 채널.send(embed=embed, view=view)
            await interaction.followup.send(f"{채널.mention} 채널에 상점 알림이 전송되었습니다!", ephemeral=True)

        except Exception as e:
            logging.error(f"상점 알림 명령어 실행 중 오류 발생: {e}", exc_info=True)
            await interaction.followup.send("오류가 발생했습니다. 관리자에게 문의하세요.", ephemeral=True)

# setup 함수 추가
async def setup(bot: commands.Bot):
    await bot.add_cog(ShopCommands(bot))
    logging.info("ShopCommands Cog 로드 완료")