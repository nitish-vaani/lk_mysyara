import os
from dataclasses import dataclass, field
from typing import Optional
import yaml
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv(dotenv_path=".env.local")

@dataclass
class LoadTestConfig:
    """Load testing specific configuration"""
    
    # Concurrency settings
    initial_concurrent_calls: int = 2
    max_concurrent_calls: int = 20  # Start smaller
    ramp_step: int = 2
    ramp_interval_minutes: int = 3
    
    # Call settings - Natural duration
    use_natural_call_duration: bool = True
    max_call_duration_seconds: int = 300  # 5 minute safety timeout
    call_gap_seconds: float = 1.0
    
    # Recovery settings
    enable_failure_recovery: bool = True
    recovery_concurrency_reduction: int = 2
    min_recovery_concurrency: int = 1
    
    # System failure thresholds
    cpu_failure_threshold: float = 95.0
    memory_failure_threshold: float = 95.0
    call_failure_rate_threshold: float = 50.0
    
    # Test settings
    csv_file_path: str = "test_data/call_list.csv"
    client_name: str = os.getenv("CLIENT_NAME", "default_client")
    test_name: str = f"load_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Reporting
    reports_directory: str = "reports"
    generate_detailed_report: bool = True

@dataclass
class EnhancedMetricsConfig:
    """Enhanced metrics configuration"""
    
    # Existing config (matching your setup)
    enabled: bool = True
    agent_name: str = "outbound-caller"
    redis_host: str = "sbi.vaaniresearch.com"
    redis_port: int = 6379
    redis_db: int = 15
    
    # Enhanced features - Client name from environment
    client_name: str = os.getenv("CLIENT_NAME", "default_client")
    store_detailed_metrics: bool = True
    
    # Dashboard settings
    monitoring_port: int = 1234
    
    # Load testing
    load_test: LoadTestConfig = field(default_factory=LoadTestConfig)
    
    @classmethod
    def from_yaml(cls, config_file: str = "config/enhanced_metrics.yml"):
        """Load from YAML file or create default"""
        if not os.path.exists(config_file):
            # Create default config
            default_config = cls()
            default_config.save_to_yaml(config_file)
            return default_config
        
        with open(config_file, 'r') as f:
            data = yaml.safe_load(f)
        
        # Handle nested load_test config
        if 'load_test' in data:
            load_test_data = data.pop('load_test')
            load_test_config = LoadTestConfig(**load_test_data)
            data['load_test'] = load_test_config
        
        return cls(**data)
    
    def save_to_yaml(self, config_file: str = "config/enhanced_metrics.yml"):
        """Save configuration to YAML"""
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        
        config_dict = {
            'enabled': self.enabled,
            'agent_name': self.agent_name,
            'redis_host': self.redis_host,
            'redis_port': self.redis_port,
            'redis_db': self.redis_db,
            'client_name': self.client_name,
            'monitoring_port': self.monitoring_port,
            'load_test': {
                'initial_concurrent_calls': self.load_test.initial_concurrent_calls,
                'max_concurrent_calls': self.load_test.max_concurrent_calls,
                'ramp_step': self.load_test.ramp_step,
                'ramp_interval_minutes': self.load_test.ramp_interval_minutes,
                'use_natural_call_duration': self.load_test.use_natural_call_duration,
                'max_call_duration_seconds': self.load_test.max_call_duration_seconds,
                'call_gap_seconds': self.load_test.call_gap_seconds,
                'enable_failure_recovery': self.load_test.enable_failure_recovery,
                'recovery_concurrency_reduction': self.load_test.recovery_concurrency_reduction,
                'min_recovery_concurrency': self.load_test.min_recovery_concurrency,
                'cpu_failure_threshold': self.load_test.cpu_failure_threshold,
                'memory_failure_threshold': self.load_test.memory_failure_threshold,
                'call_failure_rate_threshold': self.load_test.call_failure_rate_threshold,
                'csv_file_path': self.load_test.csv_file_path,
                'client_name': self.load_test.client_name,
                'test_name': self.load_test.test_name,
                'reports_directory': self.load_test.reports_directory,
                'generate_detailed_report': self.load_test.generate_detailed_report
            }
        }
        
        with open(config_file, 'w') as f:
            yaml.dump(config_dict, f, default_flow_style=False, indent=2)