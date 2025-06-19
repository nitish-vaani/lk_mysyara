import os
from dataclasses import dataclass
from typing import Optional
import yaml
from dotenv import load_dotenv

load_dotenv()

@dataclass
class MetricsConfig:
    """Centralized metrics configuration - Customized for your environment"""
    
    # Core Settings
    enabled: bool = True
    agent_name: str = "outbound-caller"
    
    # Redis Configuration - CUSTOMIZED for your setup
    redis_host: str = "sbi.vaaniresearch.com"
    redis_port: int = 6379
    redis_db: int = 15  # Using DB 15 to avoid conflicts
    redis_ttl_hours: int = 24
    
    # Database Configuration
    database_enabled: bool = False
    database_type: str = "none"
    database_url: Optional[str] = None
    
    # Monitoring API - CUSTOMIZED for your available ports
    monitoring_enabled: bool = True
    monitoring_port: int = 1234  # Using your available port
    monitoring_host: str = "0.0.0.0"
    
    # Collection Settings
    collect_system_metrics: bool = True
    collect_call_metrics: bool = True
    system_metrics_interval: int = 60
    
    # Performance Thresholds
    cpu_warning_threshold: float = 75.0
    cpu_critical_threshold: float = 90.0
    memory_warning_threshold: float = 80.0
    memory_critical_threshold: float = 90.0
    
    # Load Testing
    max_concurrent_calls: int = 50
    target_calls_for_test: int = 500
    
    # Logging
    log_level: str = "INFO"
    detailed_logging: bool = False
    
    @classmethod
    def from_env(cls) -> 'MetricsConfig':
        """Create config from environment variables"""
        return cls(
            enabled=os.getenv("METRICS_ENABLED", "true").lower() == "true",
            agent_name=os.getenv("AGENT_NAME", "outbound-caller"),
            redis_host=os.getenv("REDIS_HOST", "sbi.vaaniresearch.com"),
            redis_port=int(os.getenv("REDIS_PORT", "6379")),
            redis_db=int(os.getenv("REDIS_DB", "15")),
            database_enabled=os.getenv("DATABASE_ENABLED", "false").lower() == "true",
            monitoring_port=int(os.getenv("MONITORING_PORT", "1234")),
            max_concurrent_calls=int(os.getenv("MAX_CONCURRENT_CALLS", "50")),
            target_calls_for_test=int(os.getenv("TARGET_CALLS_FOR_TEST", "500")),
            log_level=os.getenv("METRICS_LOG_LEVEL", "INFO"),
        )
    
    @classmethod
    def from_yaml(cls, config_file: str = "config/metrics.yml") -> 'MetricsConfig':
        """Create config from YAML file"""
        if not os.path.exists(config_file):
            default_config = cls()
            default_config.save_to_yaml(config_file)
            return default_config
        
        with open(config_file, 'r') as f:
            data = yaml.safe_load(f)
        
        return cls(**data)
    
    def save_to_yaml(self, config_file: str = "config/metrics.yml"):
        """Save current config to YAML file"""
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        
        config_dict = {
            'enabled': self.enabled,
            'agent_name': self.agent_name,
            'redis_host': self.redis_host,
            'redis_port': self.redis_port,
            'redis_db': self.redis_db,
            'database_enabled': self.database_enabled,
            'monitoring_port': self.monitoring_port,
            'collect_system_metrics': self.collect_system_metrics,
            'collect_call_metrics': self.collect_call_metrics,
            'system_metrics_interval': self.system_metrics_interval,
            'cpu_warning_threshold': self.cpu_warning_threshold,
            'memory_warning_threshold': self.memory_warning_threshold,
            'max_concurrent_calls': self.max_concurrent_calls,
            'target_calls_for_test': self.target_calls_for_test,
            'log_level': self.log_level,
            'detailed_logging': self.detailed_logging
        }
        
        with open(config_file, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False, indent=2)

# Global configuration instance
_config = None

def get_metrics_config() -> MetricsConfig:
    """Get the global metrics configuration"""
    global _config
    if _config is None:
        try:
            _config = MetricsConfig.from_yaml()
        except:
            _config = MetricsConfig.from_env()
    return _config

def reload_config():
    """Reload configuration"""
    global _config
    _config = None
    return get_metrics_config()
