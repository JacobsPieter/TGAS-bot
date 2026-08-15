import logging
from typing import Any, List, Sequence, cast
from dataclasses import dataclass
import re


import discord
from discord import app_commands
from discord.ext import tasks, commands

from google.oauth2 import service_account
from googleapiclient.discovery import build

import utils.database as db
import utils.added_exceptions as excepts
import utils.discordutils as dc_utils
from utils.added_exceptions import handle_loop_errors
import utils.paths as paths

logger = logging.getLogger(name=__name__)


MAX_CHARS_PER_DISCORD_MESSAGE = 4000
MAX_ELEMENTS_PER_LAYOUTVIEW = 40


SCOPES = ["https://www.googleapis.com/auth/documents.readonly"]

credentials = service_account.Credentials.from_service_account_file(
    paths.PERSISTENT_CREDENTIAL_CONFIGS / "tgas-bot-test-40115adbe3de.json",
    scopes=SCOPES
)

service = build("docs", "v1", credentials=credentials)


def init_database(database_path = paths.DATABASE):
    global meta, info_messages_db # pylint: disable=global-variable-undefined

    p = database_path

    meta = db.MetaTable(p)

    info_messages_db = db.UpdatingTable('info_messages', p)



@dataclass
class DocElement:
    pass


@dataclass
class TextStyle(DocElement):
    bold: bool = False
    italic: bool = False
    underline: bool = False
    link: str | None = None


@dataclass
class TextRun(DocElement):
    text: str
    style: TextStyle


@dataclass
class TextDocElement(DocElement):
    text: list[TextRun]

@dataclass
class Paragraph(TextDocElement):
    text: list[TextRun]

@dataclass
class Header(TextDocElement):
    text: list[TextRun]
    level: int


@dataclass
class Bullet(TextDocElement):
    text: list[TextRun]
    nesting_level: int = 0


@dataclass
class Image(DocElement):
    object_id: str
    url: str


@dataclass
class Page:
    elements: list[DocElement]




class InfoMessageCog(commands.Cog):
    def __init__(self, bot: discord.Client):
        self.bot = bot

    async def cog_load(self) -> None:
        self.startup.start()


    @tasks.loop(count=1)
    @handle_loop_errors(logger=logger)
    async def startup(self):
        doc_id = meta.get_other(meta.OtherKeys.INFOMESSAGES_UPDATING_GOOGLEDOC_ID)
        if doc_id is None:
            raise excepts.MetaKeyNotConfiguredError(key=meta.OtherKeys.INFOMESSAGES_UPDATING_GOOGLEDOC_ID)
        doc = service.documents().get(documentId=doc_id, includeTabsContent=True).execute()
        document = parse(doc['tabs'][0])
        pages = paginate(document)
        self.bot.add_view(DynamicInfoView(pages))

    @app_commands.command(name='refresh_forum_info_views')
    async def refresh_info_views(self, interaction: discord.Interaction):
        await interaction.response.send_message(content='ㅤ', ephemeral=True, delete_after=True)
        doc_id = meta.get_other(meta.OtherKeys.INFOMESSAGES_UPDATING_GOOGLEDOC_ID)
        if doc_id is None:
            raise excepts.MetaKeyNotConfiguredError(key=meta.OtherKeys.INFOMESSAGES_UPDATING_GOOGLEDOC_ID)
        doc = service.documents().get(documentId=doc_id, includeTabsContent=True).execute()
        guild = dc_utils.get_guild(self.bot, meta)
        for tab in iter_tabs(doc["tabs"]):
            title = tab["tabProperties"]["title"]
            content = tab["documentTab"]["body"]["content"]

            if 'IGNORE ME' in get_text(content).strip()[:20]:
                continue

            document = parse(tab)
            pages = paginate(document)
            dynamic_info_view = DynamicInfoView(pages)

            try:
                message_db_res = info_messages_db.fetchone('message_name', title)
                if message_db_res is None:
                    raise excepts.InfoMessageNotConfiguredError(title)
                channel_id = message_db_res['channel_id']
                message_id = message_db_res['message_id']
                try:
                    channel = await dc_utils.get_textchannel_by_id(channel_id, self.bot)
                    try:
                        message = await channel.fetch_message(message_id)
                        await message.edit(view=dynamic_info_view)
                    except discord.NotFound:
                        logger.info("it couldn't find the message")
                        await ask_channel_to_send(interaction, title, dynamic_info_view, self.bot)
                except TypeError:
                    try:
                        message = await get_forum_message(self.bot, channel_id, message_id, title)
                        await message.edit(view=dynamic_info_view)
                    except discord.NotFound:
                        logger.info("It couldn't find the message")
                        await ask_channel_to_send(interaction, title, dynamic_info_view, self.bot)
            except excepts.ThreadChannelNotFoundError:
                logger.info("It couldn't find the thread channel")
                await ask_channel_to_send(interaction, title, dynamic_info_view, self.bot)
            except excepts.InfoMessageNotConfiguredError:
                logger.info("info message not configured")
                await ask_channel_to_send(interaction, title, dynamic_info_view, self.bot)
            except excepts.ForumMessageNotFoundError:
                logger.info("it couldn't find the forum message")
                await ask_channel_to_send(interaction, title, dynamic_info_view, self.bot)


async def ask_channel_to_send(interaction: discord.Interaction, title: str, dynamic_info_view, bot):
    await interaction.followup.send(view=ChannelQueryView(title, dynamic_info_view, bot), ephemeral=True)

class ChannelQueryView(discord.ui.LayoutView):
    def __init__(self, title, dynamic_info_view, bot):
        super().__init__()
        self.add_item(
            discord.ui.TextDisplay(
                content=f'Where do you want to send {title}'
            )
        )
        self.add_item(
            discord.ui.ActionRow(
                self.ChannelSelector(title, dynamic_info_view, bot)
            )
        )

    class ChannelSelector(discord.ui.ChannelSelect):
        def __init__(self, title, dynamic_info_view, bot):
            super().__init__()
            self.title = title
            self.dynamic_info_view = dynamic_info_view
            self.bot = bot
            self.channel_types = [discord.ChannelType.text, discord.ChannelType.forum]
            self.required = True

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.defer()
            channel = self.values[0]
            if channel.type == discord.ChannelType.forum:
                send_channel = await dc_utils.get_forumchannel_by_id(channel.id, self.bot)
                #send_channel = cast(discord.ForumChannel, channel)
                message = await send_channel.create_thread(name=self.title, view=self.dynamic_info_view)
                info_messages_db.update('message_name', self.title, columns={'channel_id': message[0].id, 'message_id': message[1].id})
            elif channel.type == discord.ChannelType.text:
                #send_channel = cast(discord.TextChannel, channel)
                send_channel = await dc_utils.get_textchannel_by_id(channel.id, self.bot)
                message = await send_channel.send(view=self.dynamic_info_view)
                info_messages_db.update('message_name', self.title, columns={'channel_id': send_channel.id, 'message_id': message.id})
            await interaction.followup.send(content=f'Sent {self.title}', ephemeral=True)


class DynamicInfoView(discord.ui.LayoutView):
    def __init__(self, pages: list[Page], current_page: int = 0):
        super().__init__(timeout=None)
        self.pages = pages
        self.page = current_page

        self.render_page()

    def render_page(self):

        self.clear_items()

        page = self.pages[self.page]
        text = ""

        for element in page.elements:

            if isinstance(element, TextDocElement):
                text = '\n'.join((text, render_text_element(element))).strip()
            if isinstance(element, Image):
                if text:
                    self.add_item(discord.ui.TextDisplay(content=text))
                    text = ""
                    self.add_item(
                        discord.ui.MediaGallery(
                            discord.MediaGalleryItem(
                                media=element.url
                            )
                        )
                    )
                else:
                    self.add_item(
                        discord.ui.MediaGallery(
                                discord.MediaGalleryItem(
                                media=element.url
                                )
                        )
                    )
        if text:
            self.add_item(discord.ui.TextDisplay(content=text))

        if len(self.pages) > 1:
            actionrow = discord.ui.ActionRow()
            first_page = self.page == 0
            last_page = self.page == len(self.pages) - 1
            self.add_item(
                discord.ui.ActionRow(
                    self.PreviousPageButton(self.pages, self.page, disabled=first_page),
                    self.PageViewButton(self.pages, self.page),
                    self.NextPageButton(self.pages, self.page, disabled=last_page)
                )
            )

    class PreviousPageButton(discord.ui.Button):
        def __init__(self, pages, page, disabled: bool):
            super().__init__()
            self.pages = pages
            self.page = page
            self.disabled = disabled
            self.style = discord.ButtonStyle.gray
            self.emoji = '◀️'

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.edit_message(view=DynamicInfoView(self.pages, self.page - 1))

    class PageViewButton(discord.ui.Button):
        def __init__(self, pages, page):
            super().__init__()
            self.disabled = True
            self.style = discord.ButtonStyle.gray
            self.label = f'{page + 1}/{len(pages)}'


    class NextPageButton(discord.ui.Button):
        def __init__(self, pages, page, disabled: bool):
            super().__init__()
            self.pages = pages
            self.page = page
            self.disabled = disabled
            self.style = discord.ButtonStyle.gray
            self.emoji = '▶️'

        async def callback(self, interaction: discord.Interaction):
            await interaction.response.edit_message(view=DynamicInfoView(self.pages, self.page + 1))



def iter_tabs(tabs):
    for tab in tabs:
        yield tab
        yield from iter_tabs(tab.get("childTabs", []))



def paginate(elements: list[DocElement]) -> list[Page]:
    pages = []

    current_page = []
    current_length = 0

    for element in elements:

        if isinstance(element, TextDocElement):

            if isinstance(element, Header) and element.level == 1 and current_page != []:
                pages.append(Page(current_page))

                current_page = []
                current_length = 0

            rendered = render_text_element(element)


            if current_length + len(rendered) + 1 > MAX_CHARS_PER_DISCORD_MESSAGE:

                pages.append(Page(current_page))

                current_page = []
                current_length = 0

            current_length += len(rendered) + 1

        current_page.append(element)


    if current_page:
        pages.append(Page(current_page))

    return pages


def parse(tab) -> list[DocElement]:
    document: list[DocElement] = []
    content = tab["documentTab"]["body"]["content"]
    for item in content:
        if 'paragraph' in item:
            textruns: list[TextRun] = []
            for element in item['paragraph']['elements']:
                if 'textRun' in element:
                    textrun: dict = element['textRun']
                    textstyle: dict = textrun['textStyle']
                    text_style = TextStyle()
                    text_style.bold = textstyle.get('bold', False)
                    text_style.italic = textstyle.get('italic', False)
                    text_style.underline = textstyle.get('underline', False)
                    text_style.link = textstyle.get('link')
                    textruns.append(TextRun(text=textrun['content'].strip('\n'), style=text_style))

                if 'inlineObjectElement' in element:
                    inlineobjectelement = element['inlineObjectElement']
                    object_id = inlineobjectelement['inlineObjectId']
                    inline_objects = tab["documentTab"]['inlineObjects']
                    image_data = inline_objects[object_id]["inlineObjectProperties"]["embeddedObject"]
                    url = image_data.get("imageProperties", {}).get("contentUri")
                    image = Image(object_id, url)
                    document.append(image)
            paragraph_data = item["paragraph"]
            style = paragraph_data.get("paragraphStyle", {}).get("namedStyleType","NORMAL_TEXT")
            if style.startswith("HEADING_"):
                level = int(style.split("_")[1])
                document.append(Header(textruns, level))
            elif "bullet" in paragraph_data:
                document.append(Bullet(textruns, paragraph_data["bullet"].get("nestingLevel", 0)))
            else:
                document.append(Paragraph(textruns))
    return document


def render_text_element(text_element: TextDocElement) -> str:
    text = ''
    for textrun in text_element.text:
        added_text = f"{'__' if textrun.style.underline and not textrun.style.link else ''}{textrun.text}{'__' if textrun.style.underline and not textrun.style.link else ''}"
        added_text = f"{'*' if textrun.style.italic else ''}{added_text}{'*' if textrun.style.italic else ''}"
        added_text = f"{'**' if textrun.style.bold else ''}{added_text}{'**' if textrun.style.bold else ''}"
        text += added_text
    if isinstance(text_element, Bullet):
        text = '- ' + text
    elif isinstance(text_element, Header):
        text = '#' * (text_element.level) + ' ' + text
    text = resolve_mentions(text)
    return text

ROLE_MENTION_PATTERN = re.compile(r'@role\[([^\]]+)\]')
USER_MENTION_PATTERN = re.compile(r'@user\[([^\]]+)\]')


def resolve_mentions(text: str) -> str:
    guild = dc_utils.get_guild(info_message_cog.bot, meta)

    def replace_role(match: re.Match) -> str:
        role_name = match.group(1).strip()

        roles = [role for role in guild.roles if role.name == role_name]

        if not roles:
            logger.warning(
                "Could not find role '%s' in guild '%s'",
                role_name,
                guild.name
            )
            return match.group(0)

        if len(roles) > 1:
            logger.warning(
                "Multiple roles named '%s' found in guild '%s'",
                role_name,
                guild.name
            )
            return match.group(0)

        return roles[0].mention

    def replace_user(match: re.Match) -> str:
        username = match.group(1).strip()

        # First try username
        members = [
            member for member in guild.members
            if member.name == username
        ]

        # Then try display name
        if not members:
            members = [
                member for member in guild.members
                if member.display_name == username
            ]

        if not members:
            logger.warning(
                "Could not find user '%s' in guild '%s'",
                username,
                guild.name
            )
            return match.group(0)

        if len(members) > 1:
            logger.warning(
                "Multiple users matching '%s' found in guild '%s'",
                username,
                guild.name
            )
            return match.group(0)

        return members[0].mention

    text = ROLE_MENTION_PATTERN.sub(replace_role, text)
    text = USER_MENTION_PATTERN.sub(replace_user, text)

    return text

async def get_forum_message(bot, channel_id, message_id, message) -> discord.Message:
    channel = await dc_utils.get_thread_by_id(channel_id, bot)
    try:
        return_message = await channel.fetch_message(message_id)
    except discord.NotFound as e:
        raise excepts.ForumMessageNotFoundError(message, message_id) from e
    return return_message


def get_text(content):
    text = ""

    for item in content:
        if "paragraph" not in item:
            continue

        for element in item["paragraph"]["elements"]:
            if "textRun" in element:
                text += element["textRun"]["content"]

    return text




def main(global_bot):
    global info_message_cog # pylint: disable=global-variable-undefined
    init_database()
    info_message_cog = InfoMessageCog(bot=global_bot)



async def setup(global_bot):
    main(global_bot=global_bot)
    await global_bot.add_cog(info_message_cog)

