import os
import logging
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.paginator import Paginator
from django.conf import settings
from django.http import Http404

logger = logging.getLogger(__name__)


class LogView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """
    View for displaying application logs - only accessible by superusers
    """
    template_name = 'main/logs.html'
    
    def test_func(self):
        """Only superusers can access logs"""
        return self.request.user.is_superuser
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get log type from URL parameter (default to 'django')
        log_type = self.request.GET.get('type', 'django')
        page_number = self.request.GET.get('page', 1)
        
        # Define available log files
        log_files = {
            'django': 'logs/django.log',
            'email': 'logs/email.log',
        }
        
        if log_type not in log_files:
            raise Http404("Log type not found")
        
        log_file_path = log_files[log_type]
        full_log_path = os.path.join(settings.BASE_DIR, log_file_path)
        
        # Check if log file exists
        if not os.path.exists(full_log_path):
            context.update({
                'log_type': log_type,
                'log_content': [],
                'log_file_exists': False,
                'log_file_path': log_file_path,
                'available_logs': list(log_files.keys()),
                'error_message': f"Log file {log_file_path} does not exist yet."
            })
            return context
        
        try:
            # Read log file content
            with open(full_log_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            # Reverse lines to show newest first
            lines.reverse()
            
            # Parse log lines and extract information
            log_entries = []
            for line in lines:
                line = line.strip()
                if line:
                    # Try to parse log line format: LEVEL TIMESTAMP MODULE PROCESS THREAD MESSAGE
                    parts = line.split(' ', 5)
                    if len(parts) >= 6:
                        level = parts[0]
                        timestamp = f"{parts[1]} {parts[2]}"
                        module = parts[3]
                        process = parts[4]
                        thread = parts[5].split(' ', 1)[0] if ' ' in parts[5] else parts[5]
                        message = parts[5].split(' ', 1)[1] if ' ' in parts[5] else parts[5]
                        
                        log_entries.append({
                            'level': level,
                            'timestamp': timestamp,
                            'module': module,
                            'process': process,
                            'thread': thread,
                            'message': message,
                            'raw_line': line
                        })
                    else:
                        # If parsing fails, treat as raw line
                        log_entries.append({
                            'level': 'INFO',
                            'timestamp': '',
                            'module': '',
                            'process': '',
                            'thread': '',
                            'message': line,
                            'raw_line': line
                        })
            
            # Paginate log entries
            paginator = Paginator(log_entries, 50)  # 50 entries per page
            page_obj = paginator.get_page(page_number)
            
            context.update({
                'log_type': log_type,
                'log_content': page_obj,
                'log_file_exists': True,
                'log_file_path': log_file_path,
                'available_logs': list(log_files.keys()),
                'total_entries': len(log_entries),
                'page_obj': page_obj,
            })
            
        except Exception as e:
            logger.error(f"Error reading log file {full_log_path}: {str(e)}")
            context.update({
                'log_type': log_type,
                'log_content': [],
                'log_file_exists': True,
                'log_file_path': log_file_path,
                'available_logs': list(log_files.keys()),
                'error_message': f"Error reading log file: {str(e)}"
            })
        
        return context
