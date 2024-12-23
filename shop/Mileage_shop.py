import logging
import discord
from discord import app_commands
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

        # 버튼 초기화...
        self.product_info_button = discord.ui.Button(
            label="🛒상품 정보",
            style=discord.ButtonStyle.primary,
            custom_id="shop_product_info"
        )
        self.product_info_button.callback = self.show_product_info
        self.add_item(self.product_info_button)

        self.mileage_button = discord.ui.Button(
            label="⭐마일리지 보기",
            style=discord.ButtonStyle.secondary,
            custom_id="show_mileage"
        )
        self.mileage_button.callback = self.show_mileage
        self.add_item(self.mileage_button)

        # 나머지 버튼들 초기화...
        self.previous_page_button = discord.ui.Button(
            label="⬅️ 이전",
            style=discord.ButtonStyle.secondary,
            custom_id="shop_previous_page"
        )
        self.previous_page_button.callback = self.previous_page
        
        self.page_info_button = discord.ui.Button(
            label=f"1/{self.max_pages}",
            style=discord.ButtonStyle.grey,
            disabled=True,
            custom_id="shop_page_info"
        )
        
        self.next_page_button = discord.ui.Button(
            label="➡️ 다음",
            style=discord.ButtonStyle.secondary,
            custom_id="shop_next_page"
        )
        self.next_page_button.callback = self.next_page
        
        self.purchase_item_button = discord.ui.Button(
            label="💲상품 구매",
            style=discord.ButtonStyle.success,
            custom_id="shop_purchase"
        )
        self.purchase_item_button.callback = self.show_purchase_modal

        self.buttons_hidden = True

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

            # 디스코드 닉네임에서 유효한 단어만 추출
            def extract_valid_nickname(display_name):
                # 닉네임을 공백으로 분리
                parts = display_name.split()
                valid_parts = []

                for part in parts:
                    # 숫자가 포함된 단어는 제외
                    if any(char.isdigit() for char in part):
                        continue
                    # 성별 표시 단어 '남', '여' 제외
                    if part in ['남', '여']:
                        continue
                    # 롤 티어 스펠링 약자 'M', 'P' 제외
                    if part in ['M', 'P', 'D', 'G', 'E', 'GM']:
                        continue
                    # 유효한 단어만 추가
                    valid_parts.append(part)

                # 유효한 단어들을 공백으로 연결하여 반환
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

            # 닉네임 비교 (공백 포함 상태로 정확힀 일치하도록)
            for row in member_data:
                if len(row) >= 3:
                    # 시트 닉네임에서 핵심 닉네임 추출
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

            # 닉네임이 일치하지 않는 경우 경고
            logging.warning("닉네임 '%s'에 대한 마일리지 정보 없음", discord_nickname)
            await interaction.followup.send(
                f"{interaction.user.mention}님의 마일리지 정보를 찾을 수 없습니다.",
                ephemeral=True
            )
        except Exception as e:
            logging.error("마일리지 보기 중 오류 발생: %s", e, exc_info=True)
            try:
                await interaction.followup.send(f"마일리지 조회 중 오류가 발생했습니다: {str(e)}", ephemeral=True)
            except discord.errors.InteractionResponded:
                logging.warning("마일리지 보기 - 이미 응답된 상호작용")

    async def show_product_info(self, interaction: discord.Interaction):
        """상품 정보를 표시하고 버튼을 추가"""
        if self.buttons_hidden:
            # 기존 버튼들을 모두 제거
            self.clear_items()
            
            # 필요한 버튼들을 다시 추가
            self.add_item(self.previous_page_button)
            self.add_item(self.page_info_button)
            self.add_item(self.next_page_button)
            self.add_item(self.purchase_item_button)
            
            self.buttons_hidden = False

        await interaction.response.send_message(embed=await self.generate_embed(), view=self, ephemeral=True)

    async def previous_page(self, interaction: discord.Interaction):
        if self.page > 0:
            self.page -= 1
            self.page_info_button.label = f"{self.page + 1}/{self.max_pages}"
        await interaction.response.edit_message(embed=await self.generate_embed(), view=self)

    async def next_page(self, interaction: discord.Interaction):
        if self.page < self.max_pages - 1:
            self.page += 1
            self.page_info_button.label = f"{self.page + 1}/{self.max_pages}"
        await interaction.response.edit_message(embed=await self.generate_embed(), view=self)

    async def show_purchase_modal(self, interaction: discord.Interaction):
        await interaction.response.send_modal(ProductNumberInput(self))

    async def process_purchase(self, interaction: discord.Interaction, product_number: str):
        """상품 구매 처리"""
        try:
            await interaction.response.defer(ephemeral=True)

            # 디스코드 닉네임에서 유효한 단어만 추출
            def extract_valid_nickname(display_name):
                parts = display_name.split()
                valid_parts = []
                for part in parts:
                    if any(char.isdigit() for char in part):  # 숫자 포함 단어 제외
                        continue
                    if part in ['남', '여']:  # 성별 단어 제외
                        continue
                    if part in ['M', 'P', 'D', 'E', 'G', 'GM', 'C']:  # 롤 티어 약자 제외
                        continue
                    valid_parts.append(part)
                return ' '.join(valid_parts).strip()

            # 닉네임 추출
            discord_nickname = extract_valid_nickname(interaction.user.display_name)
            logging.debug("추출된 닉네임: '%s'", discord_nickname)

            # Google Sheets 데이터 가져오기
            member_data = sheets_manager.get_values(sheet_name="MEMBER", range_notation="D2:P1000")
            shop_data = sheets_manager.get_values(sheet_name="상점", range_notation="J2:L100")

            if not member_data or not shop_data:
                await interaction.followup.send("데이터를 불러오는데 실패했습니다.", ephemeral=True)
                logging.error("데이터 조회 실패")
                return

            # 구매하려는 상품 정보 검색
            product = next((row for row in shop_data if len(row) >= 3 and row[0].strip() == product_number.strip()), None)
            if not product:
                await interaction.followup.send("해당 상품 번호를 찾을 수 없습니다.", ephemeral=True)
                logging.warning("상품 번호 '%s'를 찾을 수 없음", product_number)
                return

            def extract_number(value):
                if not value:
                    return 0
                number_str = ''.join(filter(str.isdigit, str(value)))
                return int(number_str) if number_str else 0

            # 사용자 정보 검색
            user_row = None
            current_balance = 0
            for idx, row in enumerate(member_data):
                if len(row) >= 3:
                    sheet_nickname = row[0].split('#')[0].strip()  # 시트 닉네임 추출
                    logging.debug("비교: 디스코드 닉네임 '%s' vs 시트 닉네임 '%s'", discord_nickname, sheet_nickname)
                    if sheet_nickname == discord_nickname:
                        user_row = idx + 2  # Google Sheets 행 번호 (1부터 시작)
                        current_balance = extract_number(row[2])  # 보유 마일리지
                        break

            if user_row is None:
                await interaction.followup.send("회원 정보를 찾을 수 없습니다.", ephemeral=True)
                logging.warning("닉네임 '%s'에 대한 회원 정보 없음", discord_nickname)
                return

            # 상품 가격 확인
            product_cost = extract_number(product[2])
            if product_cost == 0:
                await interaction.followup.send("상품 가격 정보가 올바르지 않습니다.", ephemeral=True)
                logging.warning("상품 가격 정보가 올바르지 않음: %s", product)
                return

            if current_balance < product_cost:
                await interaction.followup.send(
                    f"마일리지가 부족합니다. (현재 잔액: `{current_balance}`, 필요 마일리지: `{product_cost}`)",
                    ephemeral=True
                )
                logging.warning("잔액 부족 - 현재 잔액: %d, 필요 마일리지: %d", current_balance, product_cost)
                return

            # 마일리지 차감
            negative_cost = -abs(int(product_cost))
            current_p_value = sheets_manager.get_values(sheet_name="MEMBER", range_notation=f"P{user_row}:P{user_row}")

            if current_p_value and len(current_p_value[0]) > 0 and current_p_value[0][0].strip():
                try:
                    current_value = int(current_p_value[0][0].strip())
                    new_value = current_value + negative_cost
                except ValueError:
                    new_value = negative_cost
            else:
                new_value = negative_cost

            # Google Sheets 업데이트
            sheets_manager.update_cell(
                sheet_name="MEMBER",
                start_column="P",
                start_row=user_row,
                values=[[str(new_value)]]
            )
            new_balance = current_balance - product_cost

            # 성공 메시지
            await interaction.followup.send(
                f"{interaction.user.mention}, '{product[1]}' 상품을 성공적으로 구매했습니다!\n"
                f"차감된 마일리지: `{product_cost}`\n남은 마일리지: `{new_balance}`",
                ephemeral=True
            )

            # 로그 채널에 로그 메시지 전송
            log_channel = interaction.guild.get_channel(LOG_CHANNEL_ID)
            if log_channel:
                log_embed = discord.Embed(
                    title="상품 구매 로그",
                    description="새로운 상품 구매가 발생했습니다",
                    color=discord.Color.green(),
                    timestamp=interaction.created_at
                )
                log_embed.add_field(name="구매자", value=interaction.user.mention, inline=True)
                log_embed.add_field(name="상품명", value=product[1], inline=True)
                log_embed.add_field(name="구매 비용", value=f"{product_cost} 마일리지", inline=True)
                log_embed.add_field(name="남은 마일리지", value=str(new_balance), inline=True)
                await log_channel.send(embed=log_embed)

        except Exception as e:
            logging.error("상품 구매 처리 중 오류 발생: %s", e, exc_info=True)
            try:
                await interaction.followup.send(f"상품 구매 처리 중 오류가 발생했습니다: {str(e)}", ephemeral=True)
            except discord.errors.InteractionResponded:
                logging.warning("상품 구매 처리 - 이미 응답된 상호작용")

@app_commands.command(name="상점알림", description="지정된 채널에 상점 알림을 보냅니다.")
@app_commands.describe(채널="알림을 보낼 채널을 선택하세요")
async def shop_notification(interaction: discord.Interaction, 채널: discord.TextChannel):
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
            description="아래 버튼을 클릭하여 상품 정보를 확인하거나 본인에 마일리지 정보를 확인하세요 !", 
            color=discord.Color.green()
        )
        view = PersistentShopView(shop_data)
        await 채널.send(embed=embed, view=view)
        await interaction.followup.send(f"{채널.mention} 채널에 상점 알림이 전송되었습니다!", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"오류가 발생했습니다: {str(e)}", ephemeral=True)