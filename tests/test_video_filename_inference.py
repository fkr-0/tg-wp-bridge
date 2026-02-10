from tg_wp_bridge import message_parser
from tg_wp_bridge.schemas import TgMessage, TgChat, TgVideo


def test_video_media_without_file_name_infers_mp4():
    msg = TgMessage(
        message_id=1,
        chat=TgChat(id=1, type="channel"),
        date=0,
        text="",
        video=TgVideo(file_id="vid999", mime_type="video/mp4"),
    )

    media = message_parser.collect_supported_media(msg)

    assert len(media) == 1
    assert media[0].media_type == "video"
    assert media[0].file_name == "vid999.mp4"
