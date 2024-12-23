import logging
import discord
from discord import app_commands
from dotenv import load_dotenv
from event.GoogleSheetsManager import GoogleSheetsManager
from shop.Mileage_shop import PersistentShopView  # PersistentShopView를 import
from commands.war import WarView, initialize_ongoing_war  # WarView를 import
from commands.information import InfoChangeView
import os

# 로깅 설정
logging.basicConfig(filename='app.log', level=logging.INFO)

# 환경 변수 로드
load_dotenv()
TOKEN = os.getenv("TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

SERVICE_ACCOUNT_FILE = 'resources/service_account.json'
SPREADSHEET_ID = '1AYSWQwLOA-EvMJzJ7ros27OEzrTd2hERlI2WJX32RBE'

# Google Sheets 매니저 초기화
sheets_manager = GoogleSheetsManager(SERVICE_ACCOUNT_FILE, SPREADSHEET_ID)

# 봇 설정
intents = discord.Intents.default()
intents.message_content = True
intents.messages = True
intents.guilds = True
intents.members = True
class PersistentViewManager:
    def __init__(self, bot):
        self.bot = bot
        self.views = []

    def add_view(self, view):
        """
        View를 추가하고 봇에 등록
        """
        self.views.append(view)
        self.bot.add_view(view)

    async def initialize_views(self):
        """
        Google Sheets 데이터를 사용하여 View 초기화 및 추가 View 등록.
        """
        try:
            # WarView 등록 (먼저 등록)
            war_view = WarView()
            self.add_view(war_view)
            logging.info("WarView 등록 완료.")
            info_view = InfoChangeView()
            self.add_view(info_view)
            logging.info("infoView 등록 완료")

            # 상점 View 등록
            shop_data = sheets_manager.get_values(sheet_name="상점", range_notation="J2:L100")
            if shop_data:
                shop_view = PersistentShopView(shop_data=shop_data)
                self.add_view(shop_view)
                logging.info("PersistentShopView 등록 완료.")
            else:
                logging.error("상점 데이터를 불러올 수 없습니다.")

        except Exception as e:
            logging.error(f"PersistentViewManager 초기화 중 오류 발생: {e}")


class CustomBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.view_manager = PersistentViewManager(self)

    async def setup_hook(self):
        if not GUILD_ID:
            logging.error("GUILD_ID가 설정되지 않았습니다. 초기화를 건너뜁니다.")
            return

        try:
            logging.info("명령어 초기화 및 동기화 시작...")
            guild = discord.Object(id=GUILD_ID)

            # 먼저 persistent view 등록
            await self.view_manager.initialize_views()
            logging.info("Persistent views 등록 완료")

            # 내전 상태 초기화
            initialize_ongoing_war()
            logging.info("내전 상태 초기화 완료")

            # 기존 명령어 제거 후 재등록
            self.tree.clear_commands(guild=guild)

            # 명령어 등록
            from commands.attendance import 출석
            from commands.attendance_top import 순위
            from commands.war import WarCommand
            from commands.information import 정보변경메시지
            from shop.Mileage_shop import shop_notification

            self.tree.add_command(출석, guild=guild)
            self.tree.add_command(순위, guild=guild)
            self.tree.add_command(WarCommand(), guild=guild)
            self.tree.add_command(정보변경메시지, guild=guild)
            self.tree.add_command(shop_notification, guild=guild)

            logging.info("새 명령어 등록 완료.")

            # 명령어 동기화
            await self.tree.sync(guild=guild)
            logging.info("명령어 동기화 완료!")

        except Exception as e:
            logging.error(f"명령어 설정 중 오류 발생: {e}", exc_info=True)

    async def on_ready(self):
        logging.info(f"\n{self.user} 으로 로그인했습니다!")
        logging.info(f"서버 ID: {GUILD_ID}")
        guild = self.get_guild(GUILD_ID)
        if guild:
            logging.info(f"서버 '{guild.name}'에 연결됨")
        else:
            logging.warning(f"경고: ID {GUILD_ID}인 서버를 찾을 수 없음")


if __name__ == "__main__":
    try:
        if not TOKEN:
            raise ValueError("Discord 토큰이 설정되지 않았습니다.")
        bot = CustomBot()
        bot.run(TOKEN)
    except Exception as e:
        logging.error(f"봇 실행 중 오류 발생: {e}")