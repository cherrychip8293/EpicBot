import discord
from datetime import datetime

DISCORD_CHANNELS = {
    "server": 1321426551052570644,  # 서버 입퇴장 로그 채널 ID
    "voice": 1321426608224997377,  # 음성 채널 로그 채널 ID
    "message": 1321426630069063711,  # 메시지 삭제 로그 채널 ID
    "roles": 1321426652365852723  # 역할 업데이트 로그 채널 ID
}

class ServerLogger:
    @staticmethod
    async def log_member_join(bot, member):
        embed = discord.Embed(
            title="✅ 멤버 입장",
            description=f"{member.mention} 님이 서버에 입장했습니다!",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        log_channel = bot.get_channel(DISCORD_CHANNELS["server"])
        if log_channel:
            await log_channel.send(embed=embed)

    @staticmethod
    async def log_member_leave(bot, member):
        embed = discord.Embed(
            title="❌ 멤버 퇴장",
            description=f"{member.mention} 님이 서버에서 퇴장했습니다.",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        log_channel = bot.get_channel(DISCORD_CHANNELS["server"])
        if log_channel:
            await log_channel.send(embed=embed)

class MessageLogger:
    @staticmethod
    async def log_message_delete(bot, channel_id, message_content, author):
        log_channel = bot.get_channel(DISCORD_CHANNELS["message"])
        if log_channel:
            target_channel = bot.get_channel(channel_id)
            target_channel_mention = target_channel.mention if target_channel else "알 수 없는 채널"
            embed = discord.Embed(
                title="🗑️ 메시지 삭제",
                color=discord.Color.orange(),
                timestamp=datetime.now()
            )
            embed.add_field(name="채널", value=target_channel_mention, inline=False)
            embed.add_field(name="작성자", value=author.mention, inline=False)
            embed.add_field(name="내용", value=message_content if message_content else "[내용 없음]", inline=False)
            await log_channel.send(embed=embed)

    @staticmethod
    async def log_message_edit(bot, channel_id, before_content, after_content, author):
        log_channel = bot.get_channel(DISCORD_CHANNELS["message"])
        if log_channel:
            target_channel = bot.get_channel(channel_id)
            target_channel_mention = target_channel.mention if target_channel else "알 수 없는 채널"
            embed = discord.Embed(
                title="✏️ 메시지 수정",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            embed.add_field(name="채널", value=target_channel_mention, inline=False)
            embed.add_field(name="작성자", value=author.mention, inline=False)
            embed.add_field(name="이전 내용", value=before_content if before_content else "[내용 없음]", inline=False)
            embed.add_field(name="수정된 내용", value=after_content if after_content else "[내용 없음]", inline=False)
            await log_channel.send(embed=embed)

class VoiceLogger:
    @staticmethod
    async def log_voice_join(bot, member, channel_id):
        log_channel = bot.get_channel(DISCORD_CHANNELS["voice"])
        if log_channel:
            target_channel = bot.get_channel(channel_id)
            target_channel_mention = target_channel.mention if target_channel else "알 수 없는 채널"
            embed = discord.Embed(
                title="🔊 음성 채널 입장",
                description=f"{member.mention} 님이 음성 채널 {target_channel_mention}에 입장했습니다.",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            await log_channel.send(embed=embed)

    @staticmethod
    async def log_voice_move(bot, member, before_channel_id, after_channel_id):
        log_channel = bot.get_channel(DISCORD_CHANNELS["voice"])
        if log_channel:
            before_channel = bot.get_channel(before_channel_id)
            after_channel = bot.get_channel(after_channel_id)
            before_channel_mention = before_channel.mention if before_channel else "알 수 없는 채널"
            after_channel_mention = after_channel.mention if after_channel else "알 수 없는 채널"
            embed = discord.Embed(
                title="🔄 음성 채널 이동",
                description=f"{member.mention} 님이 음성 채널을 {before_channel_mention}에서 {after_channel_mention}로 이동했습니다.",
                color=discord.Color.gold(),
                timestamp=datetime.now()
            )
            await log_channel.send(embed=embed)

    @staticmethod
    async def log_voice_leave(bot, member, channel_id):
        log_channel = bot.get_channel(DISCORD_CHANNELS["voice"])
        if log_channel:
            target_channel = bot.get_channel(channel_id)
            target_channel_mention = target_channel.mention if target_channel else "알 수 없는 채널"
            embed = discord.Embed(
                title="🔇 음성 채널 퇴장",
                description=f"{member.mention} 님이 음성 채널 {target_channel_mention}에서 퇴장했습니다.",
                color=discord.Color.purple(),
                timestamp=datetime.now()
            )
            await log_channel.send(embed=embed)

class RoleLogger:
    @staticmethod
    async def log_role_update(bot, member, role_name, action):
        color = discord.Color.green() if action == "추가" else discord.Color.red()
        emoji = "➕" if action == "추가" else "➖"
        embed = discord.Embed(
            title=f"{emoji} 역할 업데이트",
            color=color,
            timestamp=datetime.now()
        )
        embed.add_field(name="대상", value=member.mention, inline=False)
        embed.add_field(name="역할", value=role_name, inline=False)
        log_channel = bot.get_channel(DISCORD_CHANNELS["roles"])
        if log_channel:
            await log_channel.send(embed=embed)