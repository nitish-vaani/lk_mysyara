# tools/basic_load_tester.py - Basic Load Testing Engine

import asyncio
import aiohttp
import csv
import json
import logging
import os
import random
import subprocess
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import yaml
from dataclasses import dataclass, asdict

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("load_tester")

@dataclass
class CallResult:
    """Result of a single call"""
    call_id: str
    phone_number: str
    name: str
    start_time: float
    end_time: Optional[float] = None
    status: str = "pending"  # pending, active, completed, failed
    room_name: str = ""
    error_message: str = ""
    duration_seconds: float = 0.0

@dataclass
class LoadTestConfig:
    """Load test configuration"""
    # Basic settings
    concurrent_calls: int = 5
    total_calls: int = 50
    call_gap_seconds: float = 2.0
    max_call_duration: int = 300  # 5 minutes
    
    # LiveKit settings
    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""
    agent_name: str = "enhanced-agent-1"
    
    # Test data
    csv_file: str = "test_data/call_list.csv"
    
    # Monitoring
    monitoring_url: str = "http://localhost:1234"
    report_interval: int = 30  # seconds

class BasicLoadTester:
    """Basic load testing engine for LiveKit agents"""
    
    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.active_calls: Dict[str, CallResult] = {}
        self.completed_calls: List[CallResult] = []
        self.start_time = time.time()
        self.test_data = []
        
        # Load test data
        self._load_test_data()
        
        logger.info(f"🎯 Load tester initialized")
        logger.info(f"📞 Target: {config.total_calls} calls, {config.concurrent_calls} concurrent")
        logger.info(f"📋 Test data: {len(self.test_data)} entries loaded")
    
    def _load_test_data(self):
        """Load test data from CSV"""
        try:
            with open(self.config.csv_file, 'r') as f:
                reader = csv.DictReader(f)
                self.test_data = list(reader)
            
            if not self.test_data:
                # Generate dummy data if CSV is empty
                self.test_data = [
                    {"name": f"TestUser{i}", "number": f"+123456789{i:02d}"}
                    for i in range(1, self.config.total_calls + 1)
                ]
                logger.info("📋 Generated dummy test data")
            
        except FileNotFoundError:
            # Generate dummy data if file doesn't exist
            self.test_data = [
                {"name": f"TestUser{i}", "number": f"+123456789{i:02d}"}
                for i in range(1, self.config.total_calls + 1)
            ]
            logger.info("📋 CSV not found, generated dummy test data")
    
    async def make_call(self, name: str, phone_number: str) -> CallResult:
        """Make a single call using LiveKit dispatch"""
        call_id = f"load_test_call_{int(time.time())}_{random.randint(1000, 9999)}"
        room_name = f"load_test_room_{call_id}"
        
        result = CallResult(
            call_id=call_id,
            phone_number=phone_number,
            name=name,
            start_time=time.time(),
            room_name=room_name
        )
        
        try:
            # LiveKit dispatch command
            command = [
                "lk", "dispatch", "create",
                "--room", room_name,
                "--agent-name", self.config.agent_name,
                "--metadata", phone_number,
                "--api-key", self.config.livekit_api_key,
                "--api-secret", self.config.livekit_api_secret,
                "--url", self.config.livekit_url
            ]
            
            logger.info(f"📞 Starting call: {name} ({phone_number})")
            
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                result.status = "active"
                logger.info(f"✅ Call started: {call_id}")
            else:
                result.status = "failed"
                result.error_message = stderr.decode()
                logger.error(f"❌ Call failed: {call_id} - {result.error_message}")
                
        except Exception as e:
            result.status = "failed"
            result.error_message = str(e)
            logger.error(f"❌ Call exception: {call_id} - {e}")
        
        return result
    
    async def monitor_call(self, call_result: CallResult):
        """Monitor a call until completion"""
        max_duration = self.config.max_call_duration
        check_interval = 10  # Check every 10 seconds
        
        try:
            for _ in range(max_duration // check_interval):
                await asyncio.sleep(check_interval)
                
                # Check if call is still active (simplified - you can enhance this)
                elapsed = time.time() - call_result.start_time
                
                # Simulate call completion after random duration (for testing)
                if elapsed > random.randint(30, 120):  # 30-120 seconds
                    call_result.status = "completed"
                    call_result.end_time = time.time()
                    call_result.duration_seconds = elapsed
                    break
            
            # If we reach here without completion, mark as timeout
            if call_result.status == "active":
                call_result.status = "timeout"
                call_result.end_time = time.time()
                call_result.duration_seconds = time.time() - call_result.start_time
                
        except Exception as e:
            call_result.status = "failed"
            call_result.error_message = str(e)
            call_result.end_time = time.time()
            call_result.duration_seconds = time.time() - call_result.start_time
        
        # Move from active to completed
        if call_result.call_id in self.active_calls:
            del self.active_calls[call_result.call_id]
        self.completed_calls.append(call_result)
        
        logger.info(f"🏁 Call ended: {call_result.call_id} - {call_result.status} ({call_result.duration_seconds:.1f}s)")
    
    async def run_load_test(self):
        """Run the main load test"""
        logger.info("🚀 Starting load test...")
        
        # Start monitoring task
        monitor_task = asyncio.create_task(self._monitoring_loop())
        
        calls_made = 0
        pending_tasks = []
        
        try:
            for entry in self.test_data[:self.config.total_calls]:
                # Wait if we're at max concurrency
                while len(self.active_calls) >= self.config.concurrent_calls:
                    await asyncio.sleep(1)
                
                # Make the call
                call_result = await self.make_call(entry['name'], entry['number'])
                
                if call_result.status == "active":
                    self.active_calls[call_result.call_id] = call_result
                    # Start monitoring this call
                    monitor_task_call = asyncio.create_task(self.monitor_call(call_result))
                    pending_tasks.append(monitor_task_call)
                else:
                    self.completed_calls.append(call_result)
                
                calls_made += 1
                logger.info(f"📊 Progress: {calls_made}/{self.config.total_calls} calls made, {len(self.active_calls)} active")
                
                # Wait before next call
                await asyncio.sleep(self.config.call_gap_seconds)
            
            # Wait for all calls to complete
            logger.info("⏳ Waiting for all calls to complete...")
            while self.active_calls:
                await asyncio.sleep(5)
                logger.info(f"⏳ Still waiting: {len(self.active_calls)} active calls")
            
            # Wait for monitoring tasks to complete
            await asyncio.gather(*pending_tasks, return_exceptions=True)
            
        except KeyboardInterrupt:
            logger.info("⛔ Load test interrupted by user")
        except Exception as e:
            logger.error(f"❌ Load test error: {e}")
        finally:
            monitor_task.cancel()
            await self._generate_report()
    
    async def _monitoring_loop(self):
        """Background monitoring and reporting"""
        try:
            while True:
                await asyncio.sleep(self.config.report_interval)
                await self._print_status()
        except asyncio.CancelledError:
            pass
    
    async def _print_status(self):
        """Print current status"""
        total_calls = len(self.active_calls) + len(self.completed_calls)
        completed_calls = len(self.completed_calls)
        success_rate = 0
        
        if completed_calls > 0:
            successful = len([c for c in self.completed_calls if c.status == "completed"])
            success_rate = (successful / completed_calls) * 100
        
        elapsed_time = time.time() - self.start_time
        
        logger.info("="*60)
        logger.info("📊 LOAD TEST STATUS")
        logger.info(f"⏰ Elapsed: {elapsed_time/60:.1f} minutes")
        logger.info(f"📞 Total calls: {total_calls}/{self.config.total_calls}")
        logger.info(f"🔴 Active calls: {len(self.active_calls)}")
        logger.info(f"✅ Completed calls: {completed_calls}")
        logger.info(f"📈 Success rate: {success_rate:.1f}%")
        logger.info(f"⚡ Calls per minute: {total_calls/(elapsed_time/60):.1f}")
        logger.info("="*60)
        
        # Try to get metrics from dashboard
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.config.monitoring_url}/api/status") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        logger.info(f"📊 Dashboard metrics: {data.get('active_calls', 0)} active, "
                                   f"{data.get('utilization_percent', 0):.1f}% utilization")
        except:
            pass  # Dashboard might not be available
    
    async def _generate_report(self):
        """Generate final test report"""
        logger.info("📋 Generating load test report...")
        
        total_calls = len(self.completed_calls)
        if total_calls == 0:
            logger.warning("⚠️ No completed calls to report")
            return
        
        # Calculate statistics
        successful_calls = [c for c in self.completed_calls if c.status == "completed"]
        failed_calls = [c for c in self.completed_calls if c.status in ["failed", "timeout"]]
        
        success_rate = (len(successful_calls) / total_calls) * 100
        avg_duration = sum(c.duration_seconds for c in successful_calls) / max(1, len(successful_calls))
        
        test_duration = time.time() - self.start_time
        calls_per_minute = total_calls / (test_duration / 60)
        
        # Print report
        logger.info("="*60)
        logger.info("📋 LOAD TEST REPORT")
        logger.info("="*60)
        logger.info(f"🎯 Test Configuration:")
        logger.info(f"   Target calls: {self.config.total_calls}")
        logger.info(f"   Concurrent calls: {self.config.concurrent_calls}")
        logger.info(f"   Call gap: {self.config.call_gap_seconds}s")
        logger.info(f"   Agent: {self.config.agent_name}")
        logger.info("")
        logger.info(f"📊 Test Results:")
        logger.info(f"   Total calls attempted: {total_calls}")
        logger.info(f"   Successful calls: {len(successful_calls)}")
        logger.info(f"   Failed calls: {len(failed_calls)}")
        logger.info(f"   Success rate: {success_rate:.1f}%")
        logger.info(f"   Average call duration: {avg_duration:.1f}s")
        logger.info(f"   Test duration: {test_duration/60:.1f} minutes")
        logger.info(f"   Calls per minute: {calls_per_minute:.1f}")
        logger.info("="*60)
        
        # Save detailed report to file
        report_file = f"load_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_data = {
            "test_config": asdict(self.config),
            "test_results": {
                "total_calls": total_calls,
                "successful_calls": len(successful_calls),
                "failed_calls": len(failed_calls),
                "success_rate": success_rate,
                "avg_duration": avg_duration,
                "test_duration": test_duration,
                "calls_per_minute": calls_per_minute
            },
            "call_details": [asdict(call) for call in self.completed_calls]
        }
        
        with open(report_file, 'w') as f:
            json.dump(report_data, f, indent=2)
        
        logger.info(f"📄 Detailed report saved: {report_file}")

def load_config_from_env() -> LoadTestConfig:
    """Load configuration from environment variables"""
    from dotenv import load_dotenv
    load_dotenv(dotenv_path=".env.local")
    
    return LoadTestConfig(
        livekit_url=os.getenv("LIVEKIT_URL", ""),
        livekit_api_key=os.getenv("LIVEKIT_API_KEY", ""),
        livekit_api_secret=os.getenv("LIVEKIT_API_SECRET", ""),
        agent_name=os.getenv("AGENT_NAME", "enhanced-agent-1"),
        concurrent_calls=int(os.getenv("CONCURRENT_CALLS", "5")),
        total_calls=int(os.getenv("TOTAL_CALLS", "20")),
        call_gap_seconds=float(os.getenv("CALL_GAP_SECONDS", "2.0")),
    )

async def main():
    """Main entry point"""
    print("🎯 Basic Load Testing Engine")
    print("="*40)
    
    # Load configuration
    config = load_config_from_env()
    
    # Validate configuration
    if not all([config.livekit_url, config.livekit_api_key, config.livekit_api_secret]):
        logger.error("❌ Missing LiveKit configuration. Check your .env.local file.")
        return
    
    # Create and run load tester
    load_tester = BasicLoadTester(config)
    await load_tester.run_load_test()

if __name__ == "__main__":
    asyncio.run(main())