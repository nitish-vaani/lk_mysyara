import sys
import os
sys.path.append('.')

from config.enhanced_metrics_config import EnhancedMetricsConfig

# Test configuration loading
config = EnhancedMetricsConfig.from_yaml()
print(f"✅ Config loaded successfully!")
print(f"   Client: {config.client_name}")
print(f"   Redis: {config.redis_host}:{config.redis_port}")
print(f"   Max Concurrency: {config.load_test.max_concurrent_calls}")
