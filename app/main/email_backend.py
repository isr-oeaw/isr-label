"""
Custom email backend with comprehensive logging
"""
import logging
from django.core.mail.backends.smtp import EmailBackend as SMTPEmailBackend
from django.core.mail.backends.console import EmailBackend as ConsoleEmailBackend
from django.conf import settings

logger = logging.getLogger('email')


class LoggingSMTPEmailBackend(SMTPEmailBackend):
    """SMTP email backend with comprehensive logging"""
    
    def send_messages(self, email_messages):
        """Send messages with logging"""
        if not email_messages:
            logger.info("No email messages to send")
            return 0
        
        logger.info(f"Attempting to send {len(email_messages)} email(s)")
        
        # Log email details
        for i, message in enumerate(email_messages):
            logger.info(f"Email {i+1}:")
            logger.info(f"  From: {message.from_email}")
            logger.info(f"  To: {', '.join(message.to)}")
            logger.info(f"  Subject: {message.subject}")
            logger.info(f"  Body length: {len(message.body) if message.body else 0} chars")
            if hasattr(message, 'alternatives') and message.alternatives:
                logger.info(f"  HTML alternative: {len(message.alternatives[0][0])} chars")
        
        try:
            # Call parent method to actually send emails
            result = super().send_messages(email_messages)
            logger.info(f"Successfully sent {result} email(s)")
            return result
        except Exception as e:
            logger.error(f"Failed to send emails: {str(e)}")
            logger.error(f"SMTP settings: host={self.host}, port={self.port}, use_tls={self.use_tls}")
            raise


class LoggingConsoleEmailBackend(ConsoleEmailBackend):
    """Console email backend with logging"""
    
    def send_messages(self, email_messages):
        """Send messages with logging"""
        if not email_messages:
            logger.info("No email messages to send (console backend)")
            return 0
        
        logger.info(f"Console backend: Would send {len(email_messages)} email(s)")
        
        # Log email details
        for i, message in enumerate(email_messages):
            logger.info(f"Console Email {i+1}:")
            logger.info(f"  From: {message.from_email}")
            logger.info(f"  To: {', '.join(message.to)}")
            logger.info(f"  Subject: {message.subject}")
            logger.info(f"  Body length: {len(message.body) if message.body else 0} chars")
            if hasattr(message, 'alternatives') and message.alternatives:
                logger.info(f"  HTML alternative: {len(message.alternatives[0][0])} chars")
        
        # Call parent method to print to console
        result = super().send_messages(email_messages)
        logger.info(f"Console backend: Printed {result} email(s) to console")
        return result
