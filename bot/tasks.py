import asyncio
from datetime import datetime, timedelta, time
from celery import shared_task
from django.utils import timezone as django_timezone
from django.conf import settings
import pytz
from asgiref.sync import sync_to_async
from core.models import TelegramUser, UserSettings, DailyInspiration, SentInspiration


def _was_inspiration_sent_today(telegram_user: TelegramUser, inspiration: DailyInspiration, language: str) -> bool:
    if settings.DEBUG:
        return False
    return SentInspiration.objects.filter(
        telegram_user=telegram_user,
        inspiration=inspiration,
        language=language,
    ).exists()


@shared_task
def send_inspirations_to_users():
    server_now = django_timezone.now()
    
    active_settings = UserSettings.objects.filter(
        is_active=True,
        telegram_user__is_active=True,
        selected_book__isnull=False,
    ).select_related("telegram_user", "selected_book")
    
    for settings_obj in active_settings:
        user_tz = settings_obj.timezone
        if not user_tz:
            user_tz = pytz.timezone("Europe/Kyiv")
        elif isinstance(user_tz, str):
            user_tz = pytz.timezone(user_tz)
        
        try:
            user_now = server_now.astimezone(user_tz)
        except (AttributeError, TypeError):
            user_tz = pytz.timezone("Europe/Kyiv")
            user_now = server_now.astimezone(user_tz)
        
        user_current_date = user_now.date()
        user_current_time = user_now.time()
        
        current_minute = user_current_time.minute
        window_start_minute = (current_minute // 5) * 5
        window_start_time = user_current_time.replace(minute=window_start_minute, second=0, microsecond=0)
        window_end_time = user_current_time.replace(second=0, microsecond=0)
        
        notification_time = settings_obj.notification_time
        
        if settings.DEBUG:
            time_in_window = notification_time <= user_current_time
        else:
            time_in_window = (
                window_start_time <= notification_time <= window_end_time
            )
        
        if time_in_window:
            inspiration = DailyInspiration.objects.filter(
                book=settings_obj.selected_book,
                date=user_current_date,
            ).first()
            
            if inspiration:
                if not _was_inspiration_sent_today(
                    settings_obj.telegram_user,
                    inspiration,
                    settings_obj.language
                ):
                    send_inspiration_to_user.delay(
                        settings_obj.telegram_user.telegram_id,
                        inspiration.id,
                        settings_obj.language,
                    )


@shared_task
def send_inspiration_to_user(telegram_id: int, inspiration_id: int, language: str):
    from bot.bot import bot
    from bot.utils import convert_html_to_telegram
    import logging

    logger = logging.getLogger(__name__)
    
    async def _send():
        try:
            def get_inspiration_data(insp_id: int, lang: str):
                inspiration = DailyInspiration.objects.select_related('book').get(id=insp_id)
                book = inspiration.book
                
                # Try to use HTML content if it exists, regardless of language
                # because it usually contains the most complete formatting.
                # If languages don't match, we still try to use it as a fallback.
                use_html = bool(inspiration.html_content)
                
                content = None
                if use_html:
                    content = convert_html_to_telegram(inspiration.html_content)
                    
                # If no HTML content or conversion resulted in empty string, fallback to text
                if not content or not content.strip():
                    content = inspiration.get_text_by_language(lang)
                
                # Final fallback to original text if language-specific text is empty
                if not content or not content.strip():
                    content = inspiration.original_text
                
                return content, book.title
            
            content, book_title = await sync_to_async(get_inspiration_data)(inspiration_id, language)
            
            if not content or not content.strip():
                logger.error(f"Inspiration {inspiration_id} has no content for language {language}")
                return

            from bot.templates.translations import get_text
            message = get_text(language, "inspiration_message", book_title=book_title, content=content)
            
            # Track if message was successfully sent
            message_sent = False
            
            try:
                await bot.send_message(chat_id=telegram_id, text=message)
                message_sent = True
            except Exception as e:
                logger.error(f"Failed to send message to {telegram_id}: {e}")
                # Try to send without HTML if it was a parse error
                if "can't parse entities" in str(e).lower() or "parse" in str(e).lower():
                    import re
                    clean_message = re.sub('<[^<]+?>', '', message)
                    try:
                        await bot.send_message(chat_id=telegram_id, text=clean_message)
                        message_sent = True
                        logger.info(f"Successfully sent cleaned message to {telegram_id} after parse error")
                    except Exception as e2:
                        logger.error(f"Failed to send cleaned message to {telegram_id}: {e2}")
                        # Message was not sent, don't save SentInspiration
                        return
            
            # Only save SentInspiration if message was successfully sent
            if message_sent:
                if not settings.DEBUG:
                    try:
                        telegram_user = TelegramUser.objects.get(telegram_id=telegram_id)
                        inspiration = DailyInspiration.objects.get(id=inspiration_id)
                        
                        # Use proper async wrapper for get_or_create
                        def _save_sent_inspiration():
                            return SentInspiration.objects.get_or_create(
                                telegram_user=telegram_user,
                                inspiration=inspiration,
                                language=language,
                            )
                        
                        sent_inspiration, created = await sync_to_async(_save_sent_inspiration)()
                        if created:
                            logger.info(
                                f"Saved SentInspiration record for user {telegram_id}, "
                                f"inspiration {inspiration_id}, language {language}"
                            )
                        else:
                            logger.warning(
                                f"SentInspiration already exists for user {telegram_id}, "
                                f"inspiration {inspiration_id}, language {language}"
                            )
                    except TelegramUser.DoesNotExist:
                        logger.error(f"TelegramUser {telegram_id} not found when saving SentInspiration")
                    except DailyInspiration.DoesNotExist:
                        logger.error(f"DailyInspiration {inspiration_id} not found when saving SentInspiration")
                    except Exception as e:
                        logger.error(
                            f"Error saving SentInspiration for user {telegram_id}, "
                            f"inspiration {inspiration_id}, language {language}: {e}",
                            exc_info=True
                        )
                else:
                    logger.debug(
                        f"DEBUG mode: Skipping SentInspiration save for user {telegram_id}, "
                        f"inspiration {inspiration_id}, language {language}"
                    )
            else:
                logger.warning(
                    f"Message was not sent to {telegram_id}, not saving SentInspiration record"
                )
        except Exception as e:
            logger.exception(f"Error in send_inspiration_to_user for user {telegram_id}: {e}")
    
    asyncio.run(_send())
