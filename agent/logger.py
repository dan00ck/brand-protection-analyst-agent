import logging
import inspect
import sys
from typing import Optional, Any, Dict
from datetime import datetime
from pathlib import Path


class Logger:
    _initialized = False
    _logger = None
    _config = {
        'enable_file_logging': False,
        'log_dir': 'logs',
        'log_level': "INFO"
    }

    @classmethod
    def configure(cls, enable_file_logging: bool = False, log_dir: str = 'logs', log_level: int = logging.DEBUG) -> None:
        """
        Args:
            enable_file_logging: Whether to write logs to a file
            log_dir: Directory for log files if file logging is enabled
            log_level: Logging level (e.g., logging.DEBUG, logging.INFO)
        """
        cls._config.update({
            'enable_file_logging': enable_file_logging,
            'log_dir': log_dir,
            'log_level': log_level
        })
        # Reset initialization to allow reconfiguration
        cls._initialized = False
        cls._logger = None

    @classmethod
    def _initialize(cls) -> None:
        """Initialize logging configuration if not already initialized."""
        if not cls._initialized:
            # Basic format for all logs
            log_format = '[%(asctime)s] %(levelname)s: %(message)s'
            datefmt = '%Y-%m-%d %H:%M:%S'

            # Start with stdout handler
            handlers = [logging.StreamHandler(sys.stdout)]

            # Add file handler if enabled
            if cls._config['enable_file_logging']:
                # Create log directory if needed
                log_dir = Path(cls._config['log_dir'])
                log_dir.mkdir(exist_ok=True)

                # Create log file with timestamp
                timestamp = datetime.now().strftime("%Y%m%d")
                log_file = log_dir / f"application_{timestamp}.log"

                handlers.append(logging.FileHandler(log_file))

            # Configure logging
            logging.basicConfig(
                level=cls._config['log_level'],
                format=log_format,
                datefmt=datefmt,
                handlers=handlers,
                force=True  # Ensure handlers are reset if reconfigured
            )

            cls._logger = logging.getLogger(__name__)
            cls._initialized = True

    @classmethod
    def _format_exception_message(cls, occurred_exception: Exception, python_script_name: str, script_line_number: int, additional_info: Optional[str] = None) -> str:
        """Format exception message with consistent structure."""
        base_message = (
            f"{type(occurred_exception).__name__} occurred in "
            f"File '{python_script_name}' at Line {script_line_number}"
        )

        if additional_info:
            base_message += f": {additional_info}"

        return f"{base_message}. Message: {str(occurred_exception)}"

    @classmethod
    def _get_caller_info(cls) -> Dict[str, Any]:
        """Get information about the calling frame."""
        caller_frame = inspect.currentframe().f_back.f_back
        return {
            'filename': Path(caller_frame.f_code.co_filename).name,
            'lineno': caller_frame.f_lineno,
        }

    @classmethod
    def trace_critical(cls, occurred_exception: Exception, python_script_name: Optional[str] = None, script_line_number: Optional[int] = None, additional_info: Optional[str] = None) -> None:
        cls._initialize()

        if python_script_name is None or script_line_number is None:
            caller_info = cls._get_caller_info()
            python_script_name = python_script_name or caller_info['filename']
            script_line_number = script_line_number or caller_info['lineno']

        message = cls._format_exception_message(
            occurred_exception,
            python_script_name,
            script_line_number,
            additional_info
        )
        cls._logger.critical(message, exc_info=True)

    @classmethod
    def trace_exception(cls, occurred_exception: Exception, python_script_name: Optional[str] = None, script_line_number: Optional[int] = None, additional_info: Optional[str] = None) -> None:
        cls._initialize()

        if python_script_name is None or script_line_number is None:
            caller_info = cls._get_caller_info()
            python_script_name = python_script_name or caller_info['filename']
            script_line_number = script_line_number or caller_info['lineno']

        message = cls._format_exception_message(
            occurred_exception,
            python_script_name,
            script_line_number,
            additional_info
        )
        cls._logger.error(message, exc_info=True)

    @classmethod
    def trace_warning_exception(cls, occurred_exception: Exception, python_script_name: Optional[str] = None, script_line_number: Optional[int] = None, additional_info: Optional[str] = None) -> None:
        cls._initialize()

        if python_script_name is None or script_line_number is None:
            caller_info = cls._get_caller_info()
            python_script_name = python_script_name or caller_info['filename']
            script_line_number = script_line_number or caller_info['lineno']

        message = cls._format_exception_message(
            occurred_exception,
            python_script_name,
            script_line_number,
            additional_info
        )
        cls._logger.warning(message)

    @classmethod
    def trace_warning_info(cls, info: str) -> None:
        cls._initialize()
        caller_info = cls._get_caller_info()
        cls._logger.warning(f"[{caller_info['filename']}:{caller_info['lineno']}] {info}")

    @classmethod
    def trace_info(cls, info: str) -> None:
        cls._initialize()
        caller_info = cls._get_caller_info()
        cls._logger.info(f"[{caller_info['filename']}:{caller_info['lineno']}] {info}")

    @classmethod
    def trace_debug(cls, info: str) -> None:
        cls._initialize()
        caller_info = cls._get_caller_info()
        cls._logger.debug(f"[{caller_info['filename']}:{caller_info['lineno']}] {info}")