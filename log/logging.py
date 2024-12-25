import discord
from discord.ext import commands
import logging

# 로깅 설정
loggers = {}

# 각 채널별로 로그를 보낼 디스코드 채널 ID 설정
DISCORD_CHANNELS = {
    "server": 1321426551052570644,  # 서버 입퇴장 로그 채널 ID
    "voice": 1321426608224997377,  # 음성 채널 로그 채널 ID
    "message": 1321426630069063711,  # 메시지 삭제 로그 채널 ID
    "roles": 1321426652365852723  # 역할 업데이트 로그 채널 ID
}

# 서버 입퇴장 로그 기능
class ServerLogger:
    @staticmethod
    async def log_member_join(bot, member_id):
        channel = bot.get_channel(DISCORD_CHANNELS["server"])
        embed = discord.Embed(
            title="회원 입장",
            description=f"<@{member_id}>님이 서버에 입장했습니다.",
            color=discord.Color.green()
        )
        await channel.send(embed=embed)

    @staticmethod
    async def log_member_leave(bot, member_id):
        channel = bot.get_channel(DISCORD_CHANNELS["server"])
        embed = discord.Embed(
            title="회원 퇴장",
            description=f"<@{member_id}>님이 서버에서 퇴장했습니다.",
            color=discord.Color.red()
        )
        await channel.send(embed=embed)

# 음성 채널 로그 기능
class VoiceLogger:
    @staticmethod
    async def log_voice_join(bot, member_id, channel_name):
        channel = bot.get_channel(DISCORD_CHANNELS["voice"])
        embed = discord.Embed(
            title="음성 채널 입장",
            description=f"<@{member_id}>님이 **{channel_name}** 채널에 입장했습니다.",
            color=discord.Color.blue()
        )
        await channel.send(embed=embed)

    @staticmethod
    async def log_voice_leave(bot, member_id, channel_name):
        channel = bot.get_channel(DISCORD_CHANNELS["voice"])
        embed = discord.Embed(
            title="음성 채널 퇴장",
            description=f"<@{member_id}>님이 **{channel_name}** 채널에서 퇴장했습니다.",
            color=discord.Color.orange()
        )
        await channel.send(embed=embed)

# 메시지 삭제 로그 기능
class MessageLogger:
    @staticmethod
    async def log_message_delete(bot, channel_name, message_content, author_id):
        channel = bot.get_channel(DISCORD_CHANNELS["message"])
        embed = discord.Embed(
            title="메시지 삭제",
            description=f"**채널**: {channel_name}\n**작성자**: <@{author_id}>\n**내용**: {message_content}",
            color=discord.Color.red()
        )
        await channel.send(embed=embed)

# 역할 업데이트 로그 기능
class RoleLogger:
    @staticmethod
    async def log_role_add(bot, member_id, role_name):
        channel = bot.get_channel(DISCORD_CHANNELS["roles"])
        embed = discord.Embed(
            title="역할 추가",
            description=f"**대상**: <@{member_id}>\n**추가된 역할**: {role_name}",
            color=discord.Color.green()
        )
        await channel.send(embed=embed)

    @staticmethod
    async def log_role_remove(bot, member_id, role_name):
        channel = bot.get_channel(DISCORD_CHANNELS["roles"])
        embed = discord.Embed(
            title="역할 제거",
            description=f"**대상**: <@{member_id}>\n**제거된 역할**: {role_name}",
            color=discord.Color.red()
        )
        await channel.send(embed=embed)

# 봇 이벤트 및 실행
def setup_loggers():
    global loggers
    loggers = {
        "server": ServerLogger,
        "voice": VoiceLogger,
        "message": MessageLogger,
        "roles": RoleLogger
    }

setup_loggers()