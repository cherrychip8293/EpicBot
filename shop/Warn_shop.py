import logging
import discord
from discord.ext import commands
from event.GoogleSheetsManager import GoogleSheetsManager

logging.basicConfig(level=logging.DEBUG, format="[%(asctime)s] [%(levelname)s] %(message)s")

SERVICE_ACCOUNT_FILE = 'resources/service_account.json'
SPREADSHEET_ID = '1AYSWQwLOA-EvMJzJ7ros27OEzrTd2hERlI2WJX32RBE'

sheets_manager = GoogleSheetsManager(SERVICE_ACCOUNT_FILE, SPREADSHEET_ID)

def clean_value(value):
    """문자열에서 특수문자를 제거하고 공백을 정리합니다."""
    if isinstance(value, str):
        # 작은따옴표와 큰따옴표 모두 제거
        cleaned = value.replace("'", "").replace('"', "").strip()
        return cleaned
    return str(value).strip()

def merge_values(existing_value, new_value):
    try:
        # 값 정리
        existing_value = clean_value(existing_value) if existing_value else "0"
        new_value = clean_value(new_value)

        # 숫자인 경우 합산
        if existing_value.replace(".", "").lstrip("-").isdigit() and new_value.replace(".", "").lstrip("-").isdigit():
            total = float(existing_value) + float(new_value)
            return str(int(total)) if total.is_integer() else str(total)
        
        # 문자열인 경우 병합
        existing_list = [clean_value(x) for x in existing_value.split(",") if clean_value(x)]
        if new_value not in existing_list:
            existing_list.append(new_value)

        # 리스트 병합 후 중복 제거
        return ", ".join(sorted(set(existing_list)))
    except Exception as e:
        logging.error(f"값 병합 중 오류 발생: {str(e)}")
        return new_value

class ApplyModal(discord.ui.Modal, title="상품 적용"):
    def __init__(self):
        super().__init__()
        self.nickname = discord.ui.TextInput(
            label="닉네임",
            placeholder="닉네임을 입력하세요",
            required=True
        )
        self.product_number = discord.ui.TextInput(
            label="상품 번호",
            placeholder="상품 번호를 입력하세요",
            required=True
        )
        self.add_item(self.nickname)
        self.add_item(self.product_number)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # 입력된 값 정리
            nickname = clean_value(self.nickname.value)
            product_number = clean_value(self.product_number.value)
            logging.debug(f"입력된 닉네임: {self.nickname.value}, 정리된 닉네임: {nickname}")
            logging.debug(f"입력된 상품 번호: {self.product_number.value}, 정리된 상품 번호: {product_number}")

            # 멤버 데이터 가져오기
            member_data = sheets_manager.get_values(sheet_name="MEMBER", range_notation="D2:O1000")
            logging.debug(f"멤버 데이터 가져옴: {member_data[:5]}")  # 데이터가 많으면 일부만 출력

            # 상점 데이터 가져오기
            shop_data = sheets_manager.get_values(sheet_name="상점", range_notation="F2:H100")
            logging.debug(f"상점 데이터 가져옴: {shop_data[:5]}")  # 데이터가 많으면 일부만 출력

            # 상품 번호로 상점에서 값 찾기
            product_row = None
            for row in shop_data:
                if len(row) >= 3 and clean_value(row[0]) == product_number:
                    product_row = row
                    break

            if not product_row:
                await interaction.response.send_message(
                    f"상품 번호 {product_number}을(를) 상점에서 찾을 수 없습니다.",
                    ephemeral=True
                )
                return

            product_value = clean_value(product_row[2])
            logging.debug(f"상품 번호 {product_number}에 해당하는 값: {product_value}")

            # 멤버 데이터에서 닉네임 찾기
            member_found = False
            for idx, row in enumerate(member_data):
                if len(row) >= 1 and clean_value(row[0]) == nickname:
                    member_found = True
                    update_row = idx + 2

                    # 기존 값 가져오기 (열 O는 인덱스 11)
                    existing_value = row[11] if len(row) >= 12 else None
                    logging.debug(f"기존 값: {existing_value}")

                    # 값 병합
                    new_value = merge_values(existing_value, product_value)
                    logging.debug(f"병합된 새 값: {new_value}")

                    # 숫자로 저장되도록 처리
                    final_value = (
                        float(new_value) if new_value.replace(".", "").lstrip("-").isdigit() 
                        else new_value
                    )
                    logging.debug(f"최종 업데이트 값: {final_value}")

                    # 업데이트 실행
                    sheets_manager.update_cell(
                        sheet_name="MEMBER",
                        start_column="O",
                        start_row=update_row,
                        values=[[final_value]],
                        value_input_option="USER_ENTERED"
                    )
                    logging.debug(f"데이터 업데이트 완료: {update_row}행, 값: {final_value}")

                    await interaction.response.send_message(
                        f"{nickname}님의 데이터가 업데이트되었습니다.\n"
                        f"기존 값: {existing_value if existing_value else '없음'}\n"
                        f"추가된 값: {product_value}\n"
                        f"최종 값: {final_value}",
                        ephemeral=True
                    )
                    break

            if not member_found:
                await interaction.response.send_message(
                    f"닉네임 {nickname}을(를) 찾을 수 없습니다.",
                    ephemeral=True
                )

        except Exception as e:
            logging.error(f"적용 처리 중 오류 발생: {str(e)}", exc_info=True)
            await interaction.response.send_message(
                "데이터 적용 중 오류가 발생했습니다. 관리자에게 문의하세요.",
                ephemeral=True
            )



class Warn_ShopView(discord.ui.View):
    def __init__(self, shop_data):
        super().__init__(timeout=None)
        self.shop_data = shop_data
        self.page = 0
        self.items_per_page = 5
        self.max_pages = max((len(self.shop_data) - 1) // self.items_per_page + 1, 1)

    async def generate_embed(self):
        embed = discord.Embed(title="상품 목록", color=discord.Color.blue())

        start_idx = self.page * self.items_per_page
        end_idx = min(start_idx + self.items_per_page, len(self.shop_data))
        page_items = self.shop_data[start_idx:end_idx]

        if not page_items:
            embed.description = "상품 정보가 없습니다."
        else:
            for row in page_items:
                embed.add_field(
                    name=f"상품 번호: {clean_value(row[0])}",
                    value=f"상품 이름: {clean_value(row[1])}\n가격: {clean_value(row[2])}",
                    inline=False
                )

        embed.set_footer(text=f"페이지 {self.page + 1}/{self.max_pages}")
        return embed

    @discord.ui.button(label="상품 목록", style=discord.ButtonStyle.primary, custom_id="product_list_button")
    async def product_list_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = Warn_ShopPaginationView(self)
        await interaction.response.send_message(embed=await self.generate_embed(), view=view, ephemeral=True)

    @discord.ui.button(label="적용", style=discord.ButtonStyle.secondary, custom_id="apply_button")
    async def apply_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            modal = ApplyModal()
            await interaction.response.send_modal(modal)
        except Exception as e:
            logging.error(f"적용 모달 생성 중 오류 발생: {str(e)}", exc_info=True)
            await interaction.response.send_message(
                "적용 기능 실행 중 오류가 발생했습니다.",
                ephemeral=True
            )

class Warn_ShopPaginationView(discord.ui.View):
    def __init__(self, shop_view: Warn_ShopView):
        super().__init__(timeout=None)
        self.shop_view = shop_view

    @discord.ui.button(label="⬅️ 이전", style=discord.ButtonStyle.secondary, row=1)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.shop_view.page > 0:
            self.shop_view.page -= 1
            await interaction.response.edit_message(embed=await self.shop_view.generate_embed(), view=self)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="➡️ 다음", style=discord.ButtonStyle.secondary, row=1)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.shop_view.page < self.shop_view.max_pages - 1:
            self.shop_view.page += 1
            await interaction.response.edit_message(embed=await self.shop_view.generate_embed(), view=self)
        else:
            await interaction.response.defer()

class Warn_ShopCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="경고상점")
    async def warn_shop(self, ctx):
        try:
            shop_data = sheets_manager.get_values(sheet_name="상점", range_notation="F2:H100")
            if not shop_data:
                await ctx.send("상품 정보가 없습니다.")
                return

            filtered_data = [row for row in shop_data if len(row) >= 3 and clean_value(row[0]).isdigit()]
            view = Warn_ShopView(shop_data=filtered_data)
            await ctx.send("상품 목록을 확인하세요.", view=view)
        except Exception as e:
            logging.error(f"경고 상점 활성화 중 오류 발생: {str(e)}", exc_info=True)
            await ctx.send("경고 상점을 활성화하는 중 오류가 발생했습니다.")

async def setup(bot: commands.Bot):
    await bot.add_cog(Warn_ShopCommands(bot))