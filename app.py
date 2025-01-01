import datetime
import logging
import re
from typing import List
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
from event.GoogleSheetsManager import GoogleSheetsManager
from shop.Mileage_shop import PersistentShopView
from commands.war import WarView, initialize_ongoing_war, WarCommand
from commands.information import InfoChangeView, InfoCommands
from log.logging import ServerLogger, VoiceLogger, MessageLogger, RoleLogger
from commands.attendance import AttendanceCommands
from shop.Mileage_shop import PersistentShopView
import os
import pytz

# 로깅 설정
logging.basicConfig(
    filename='app.log',
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logging.getLogger("discord").setLevel(logging.WARNING)

# 환경 변수 로드
load_dotenv()
TOKEN = os.getenv("TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))

# Google Sheets 설정
SERVICE_ACCOUNT_FILE = 'resources/service_account.json'
SPREADSHEET_ID = '1AYSWQwLOA-EvMJzJ7ros27OEzrTd2hERlI2WJX32RBE'

# 시간대 설정
seoul_tz = pytz.timezone("Asia/Seoul")

# Google Sheets 매니저 초기화
sheets_manager = GoogleSheetsManager(SERVICE_ACCOUNT_FILE, SPREADSHEET_ID)

class PersistentViewManager:
    def __init__(self, bot):
        self.bot = bot
        self.views = []

    def add_view(self, view):
        self.views.append(view)
        self.bot.add_view(view)

    async def initialize_views(self):
        try:
            war_view = WarView()
            self.add_view(war_view)
            logging.info("WarView 등록 완료.")

            shop_data = sheets_manager.get_values(sheet_name="상점", range_notation="J2:L100")
            if shop_data:
                shop_view = PersistentShopView(shop_data=shop_data)
                self.add_view(shop_view)
                logging.info("PersistentShopView 등록 완료.")
            else:
                logging.error("상점 데이터를 불러올 수 없습니다.")

            info_view = InfoChangeView()
            self.add_view(info_view)
            logging.info("InfoChangeView 등록 완료.")

        except Exception as e:
            logging.error(f"PersistentViewManager 초기화 중 오류 발생: {e}")

class CustomBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.messages = True
        intents.guilds = True
        intents.members = True
        intents.voice_states = True
        
        super().__init__(command_prefix="!", intents=intents)
        self.view_manager = None  # setup_hook에서 초기화
        self.guild = None
        self._synced = False
        self.setup_done = False

    async def setup_hook(self):
        if not GUILD_ID:
            logging.error("GUILD_ID가 설정되지 않았습니다.")
            return

        try:
            self.guild = self.get_guild(GUILD_ID) or discord.Object(id=GUILD_ID)
            self.view_manager = PersistentViewManager(self)

            # 내전 활성화 확인 (initialize_ongoing_war 호출)
            initialize_ongoing_war()
            logging.info("내전 활성화 상태 확인 완료")
            
            # 확장 기능 로드
            extensions: List[str] = [
                "commands.attendance",
                "commands.information",
                "commands.war",
                "commands.attendance_top",
                "shop.Mileage_shop"
            ]
            
            for extension in extensions:
                try:
                    await self.load_extension(extension)
                    logging.info(f"{extension} 확장 기능 로드 완료")
                except Exception as e:
                    logging.error(f"{extension} 로드 중 오류 발생: {e}")
                    continue

            # View 초기화
            await self.view_manager.initialize_views()
            
            self.setup_done = True
            
        except Exception as e:
            logging.error(f"봇 설정 중 오류 발생: {e}", exc_info=True)
            self.setup_done = False

    async def on_ready(self):
     if not self._synced:
        try:
            logging.info("명령어 동기화 시작...")
            
            # GUILD ID가 설정된 경우 해당 길드에만 동기화
            if GUILD_ID:
                guild = discord.Object(id=GUILD_ID)
                commands_synced = await self.tree.sync(guild=guild)
                logging.info(f"길드 ID {GUILD_ID}에 동기화된 명령어 수: {len(commands_synced)}")
            else:
                # GUILD ID가 없으면 글로벌 동기화
                commands_synced = await self.tree.sync()
                logging.info(f"글로벌로 동기화된 명령어 수: {len(commands_synced)}")
            
            self._synced = True
        except Exception as e:
            logging.error(f"명령어 동기화 중 오류 발생: {e}", exc_info=True)

        logging.info(f"\n{self.user} 으로 로그인했습니다!")
        logging.info(f"서버 ID: {GUILD_ID}")
        
        guild = self.get_guild(GUILD_ID)
        if guild:
            logging.info(f"서버 '{guild.name}'에 연결됨")
            await self.change_presence(
                activity=discord.Activity(
                    type=discord.ActivityType.watching,
                    name="길드원 관리"
                )
            )
        else:
            logging.warning(f"경고: ID {GUILD_ID}인 서버를 찾을 수 없음")

    async def on_member_join(self, member):
        await ServerLogger.log_member_join(self, member)

    async def on_member_remove(self, member):
        await ServerLogger.log_member_leave(self, member)

    async def on_message_delete(self, message):
        if message.author and hasattr(message.author, "mention"):
            await MessageLogger.log_message_delete(
                self,
                message.channel.id,
                message.content,
                message.author
            )

    async def on_message_edit(self, before, after):
        if before.content != after.content:
            await MessageLogger.log_message_edit(
                self,
                before.channel.id,
                before.content,
                after.content,
                before.author
            )

    async def on_voice_state_update(self, member, before, after):
        if before.channel != after.channel:
            if after.channel:
                if before.channel:
                    await VoiceLogger.log_voice_move(
                        self,
                        member,
                        before.channel.id,
                        after.channel.id
                    )
                else:
                    await VoiceLogger.log_voice_join(
                        self,
                        member,
                        after.channel.id
                    )
            elif before.channel:
                await VoiceLogger.log_voice_leave(
                    self,
                    member,
                    before.channel.id
                )

    async def on_member_update(self, before, after):
        added_roles = [role for role in after.roles if role not in before.roles]
        removed_roles = [role for role in before.roles if role not in after.roles]

        for role in added_roles:
            await RoleLogger.log_role_update(self, after, role.name, "추가")

        for role in removed_roles:
            await RoleLogger.log_role_update(self, after, role.name, "제거")

def main():
    try:
        if not TOKEN:
            raise ValueError("Discord 토큰이 설정되지 않았습니다.")
        
        bot = CustomBot()
        bot.run(TOKEN, log_handler=None)
        
    except Exception as e:
        logging.critical(f"봇 실행 중 치명적 오류 발생: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    main()