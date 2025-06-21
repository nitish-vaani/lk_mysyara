# tools/full_load_testing_orchestrator.py - Complete Load Testing System

import asyncio
import aiohttp
import csv
import json
import logging
import os
import psutil
import random
import subprocess
import time
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import yaml
from dataclasses import dataclass, asdict
import signal
import sys

# Add project root to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from config.enhanced_metrics_config import EnhancedMetricsConfig

# Setup comprehensive logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'load_test_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("full_load_tester")

@dataclass
class LoadTestPhase:
    """Represents a phase in the load test"""
    phase_name: str
    concurrent_calls: int
    duration_minutes: int
    calls_per_minute: float
    description: str

@dataclass
class CallResult:
    """Enhanced call result with detailed metrics"""
    call_id: str
    phone_number: str
    name: str
    start_time: float
    end_time: Optional[float] = None
    status: str = "pending"  # pending, active, completed, failed, timeout
    room_name: str = ""
    error_message: str = ""
    duration_seconds: float = 0.0
    
    # Enhanced metrics
    llm_calls: int = 0
    tts_calls: int = 0
    asr_calls: int = 0
    avg_ttft: float = 0.0
    avg_user_latency: float = 0.0
    total_interactions: int = 0
    
    # System metrics during call
    cpu_percent: float = 0.0
    memory_percent: float = 0.0

@dataclass
class LoadTestReport:
    """Comprehensive load test report"""
    test_id: str
    config: dict
    start_time: float
    end_time: float
    total_duration_minutes: float
    
    # Call statistics
    total_calls_attempted: int
    successful_calls: int
    failed_calls: int
    timeout_calls: int
    success_rate: float
    
    # Performance metrics
    avg_call_duration: float
    avg_ttft: float
    avg_user_latency: float
    total_interactions: int
    calls_per_minute: float
    
    # System performance
    peak_cpu_percent: float
    peak_memory_percent: float
    avg_cpu_percent: float
    avg_memory_percent: float
    
    # Phase results
    phase_results: List[dict]
    
    # Detailed call data
    call_results: List[CallResult]

class FullLoadTestingOrchestrator:
    """Complete load testing orchestration system"""
    
    def __init__(self, config_file: str = "config/enhanced_metrics.yml"):
        self.config = EnhancedMetricsConfig.from_yaml(config_file)
        self.test_id = f"load_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Test state
        self.active_calls: Dict[str, CallResult] = {}
        self.completed_calls: List[CallResult] = []
        self.start_time = time.time()
        self.is_running = False
        self.should_stop = False
        
        # Test data
        self.test_data = []
        self.current_phase = 0
        self.phases: List[LoadTestPhase] = []
        
        # Monitoring
        self.system_metrics = []
        self.monitoring_tasks = []
        
        # Load test data
        self._load_test_data()
        self._setup_test_phases()
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info(f"🎯 Full Load Testing Orchestrator initialized")
        logger.info(f"📋 Test ID: {self.test_id}")
        logger.info(f"📞 Target: {len(self.phases)} phases, max {max(p.concurrent_calls for p in self.phases)} concurrent")
        logger.info(f"📊 Enhanced metrics: {self.config.enabled}")
        logger.info(f"📈 Dashboard: http://localhost:{self.config.monitoring_port}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"🛑 Received signal {signum}, initiating graceful shutdown...")
        self.should_stop = True
    
    def _load_test_data(self):
        """Load test data from CSV or generate dummy data"""
        csv_file = self.config.load_test.csv_file_path
        
        try:
            with open(csv_file, 'r') as f:
                reader = csv.DictReader(f)
                self.test_data = list(reader)
            logger.info(f"📋 Loaded {len(self.test_data)} entries from {csv_file}")
        except FileNotFoundError:
            # Generate comprehensive test data
            self.test_data = [
                {
                    "name": f"LoadTestUser{i:03d}",
                    "number": f"+1{random.randint(100, 999)}{random.randint(100, 999)}{random.randint(1000, 9999)}"
                }
                for i in range(1, 1000)  # Generate 1000 test numbers
            ]
            logger.info(f"📋 Generated {len(self.test_data)} dummy test entries")
    
    def _setup_test_phases(self):
        """Setup load test phases based on configuration"""
        config = self.config.load_test
        
        # Phase 1: Ramp-up
        self.phases.append(LoadTestPhase(
            phase_name="Ramp-up",
            concurrent_calls=config.initial_concurrent_calls,
            duration_minutes=5,
            calls_per_minute=config.initial_concurrent_calls / 2,
            description="Gradual increase to initial load"
        ))
        
        # Phase 2: Sustained Load
        self.phases.append(LoadTestPhase(
            phase_name="Sustained Load",
            concurrent_calls=config.initial_concurrent_calls * 2,
            duration_minutes=15,
            calls_per_minute=config.initial_concurrent_calls,
            description="Maintain steady load"
        ))
        
        # Phase 3: Peak Load
        self.phases.append(LoadTestPhase(
            phase_name="Peak Load",
            concurrent_calls=config.max_concurrent_calls,
            duration_minutes=10,
            calls_per_minute=config.max_concurrent_calls / 2,
            description="Maximum concurrent load test"
        ))
        
        # Phase 4: Stress Test
        if config.max_concurrent_calls < 50:
            self.phases.append(LoadTestPhase(
                phase_name="Stress Test",
                concurrent_calls=min(config.max_concurrent_calls * 2, 100),
                duration_minutes=5,
                calls_per_minute=config.max_concurrent_calls,
                description="Beyond normal capacity stress test"
            ))
        
        # Phase 5: Cool-down
        self.phases.append(LoadTestPhase(
            phase_name="Cool-down",
            concurrent_calls=config.initial_concurrent_calls,
            duration_minutes=5,
            calls_per_minute=config.initial_concurrent_calls / 3,
            description="Gradual reduction to baseline"
        ))
        
        logger.info(f"🎭 Setup {len(self.phases)} test phases:")
        for i, phase in enumerate(self.phases):
            logger.info(f"   Phase {i+1}: {phase.phase_name} - {phase.concurrent_calls} concurrent, {phase.duration_minutes}min")
    
    async def make_enhanced_call(self, name: str, phone_number: str) -> CallResult:
        """Make a call with enhanced monitoring"""
        call_id = f"{self.test_id}_call_{int(time.time())}_{random.randint(1000, 9999)}"
        room_name = f"load_test_room_{call_id}"
        
        result = CallResult(
            call_id=call_id,
            phone_number=phone_number,
            name=name,
            start_time=time.time(),
            room_name=room_name,
            cpu_percent=psutil.cpu_percent(),
            memory_percent=psutil.virtual_memory().percent
        )
        
        try:
            # Use enhanced agent
            command = [
                "lk", "dispatch", "create",
                "--room", room_name,
                "--agent-name", "enhanced-agent-1",  # Use our enhanced agent
                "--metadata", phone_number,
                "--api-key", os.getenv("LIVEKIT_API_KEY"),
                "--api-secret", os.getenv("LIVEKIT_API_SECRET"),
                "--url", os.getenv("LIVEKIT_URL")
            ]
            
            logger.info(f"📞 Starting enhanced call: {name} ({phone_number})")
            
            process = await asyncio.create_subprocess_exec(
                *command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                result.status = "active"
                logger.info(f"✅ Enhanced call started: {call_id}")
            else:
                result.status = "failed"
                result.error_message = stderr.decode()
                logger.error(f"❌ Enhanced call failed: {call_id} - {result.error_message}")
                
        except Exception as e:
            result.status = "failed"
            result.error_message = str(e)
            logger.error(f"❌ Enhanced call exception: {call_id} - {e}")
        
        return result
    
    async def monitor_enhanced_call(self, call_result: CallResult):
        """Monitor call with enhanced metrics collection"""
        monitoring_url = f"http://localhost:{self.config.monitoring_port}"
        check_interval = 15  # Check every 15 seconds
        max_duration = self.config.load_test.max_call_duration_seconds
        
        try:
            for _ in range(max_duration // check_interval):
                if self.should_stop:
                    break
                    
                await asyncio.sleep(check_interval)
                
                # Get enhanced metrics from dashboard
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(f"{monitoring_url}/api/enhanced-status") as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                
                                # Find our call in active calls
                                for active_call in data.get('active_calls', []):
                                    if call_result.call_id in active_call.get('call_id', ''):
                                        # Update metrics
                                        call_result.llm_calls = active_call.get('llm_calls', 0)
                                        call_result.tts_calls = active_call.get('tts_calls', 0)
                                        call_result.asr_calls = active_call.get('asr_calls', 0)
                                        call_result.avg_ttft = active_call.get('avg_ttft', 0.0)
                                        call_result.avg_user_latency = active_call.get('avg_user_latency', 0.0)
                                        call_result.total_interactions = call_result.llm_calls + call_result.tts_calls
                                        break
                except:
                    pass  # Dashboard might not be available
                
                # Check if call completed (simplified - use natural duration)
                elapsed = time.time() - call_result.start_time
                if elapsed > random.randint(60, 180):  # 1-3 minutes
                    call_result.status = "completed"
                    call_result.end_time = time.time()
                    call_result.duration_seconds = elapsed
                    break
            
            # Handle timeout
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
        
        logger.info(f"🏁 Enhanced call ended: {call_result.call_id} - {call_result.status} "
                   f"({call_result.duration_seconds:.1f}s, {call_result.total_interactions} interactions)")
    
    async def run_phase(self, phase: LoadTestPhase) -> dict:
        """Run a single load test phase"""
        logger.info(f"🎭 Starting Phase: {phase.phase_name}")
        logger.info(f"   📞 Concurrent: {phase.concurrent_calls}")
        logger.info(f"   ⏱️ Duration: {phase.duration_minutes} minutes")
        logger.info(f"   📈 Rate: {phase.calls_per_minute} calls/minute")
        
        phase_start = time.time()
        calls_made = 0
        phase_calls = []
        pending_tasks = []
        
        # Calculate call interval
        call_interval = 60.0 / phase.calls_per_minute if phase.calls_per_minute > 0 else 5.0
        
        try:
            while (time.time() - phase_start) < (phase.duration_minutes * 60) and not self.should_stop:
                # Maintain concurrency limit
                while len(self.active_calls) >= phase.concurrent_calls:
                    if self.should_stop:
                        break
                    await asyncio.sleep(1)
                
                if self.should_stop:
                    break
                
                # Make new call
                if calls_made < len(self.test_data):
                    entry = self.test_data[calls_made % len(self.test_data)]
                    call_result = await self.make_enhanced_call(entry['name'], entry['number'])
                    
                    if call_result.status == "active":
                        self.active_calls[call_result.call_id] = call_result
                        phase_calls.append(call_result)
                        
                        # Start monitoring this call
                        monitor_task = asyncio.create_task(self.monitor_enhanced_call(call_result))
                        pending_tasks.append(monitor_task)
                    else:
                        phase_calls.append(call_result)
                        self.completed_calls.append(call_result)
                    
                    calls_made += 1
                
                # Wait before next call
                await asyncio.sleep(call_interval)
            
            # Wait for phase to complete
            phase_end_time = phase_start + (phase.duration_minutes * 60)
            while time.time() < phase_end_time and not self.should_stop:
                await asyncio.sleep(5)
                logger.info(f"🕐 Phase {phase.phase_name}: {len(self.active_calls)} active calls, "
                           f"{time.time() - phase_start:.0f}s elapsed")
            
        except Exception as e:
            logger.error(f"❌ Error in phase {phase.phase_name}: {e}")
        
        # Phase summary
        phase_duration = time.time() - phase_start
        phase_successful = len([c for c in phase_calls if c.status == "completed"])
        phase_failed = len([c for c in phase_calls if c.status in ["failed", "timeout"]])
        
        phase_result = {
            "phase_name": phase.phase_name,
            "duration_minutes": phase_duration / 60,
            "calls_attempted": len(phase_calls),
            "calls_successful": phase_successful,
            "calls_failed": phase_failed,
            "success_rate": (phase_successful / max(1, len(phase_calls))) * 100,
            "peak_concurrent": max(len(self.active_calls), phase.concurrent_calls),
            "avg_system_cpu": psutil.cpu_percent(interval=1),
            "avg_system_memory": psutil.virtual_memory().percent
        }
        
        logger.info(f"✅ Phase {phase.phase_name} completed:")
        logger.info(f"   📊 Calls: {len(phase_calls)} attempted, {phase_successful} successful")
        logger.info(f"   📈 Success rate: {phase_result['success_rate']:.1f}%")
        logger.info(f"   💻 System: CPU {phase_result['avg_system_cpu']:.1f}%, Memory {phase_result['avg_system_memory']:.1f}%")
        
        return phase_result
    
    async def run_full_load_test(self):
        """Run the complete load testing sequence"""
        logger.info("🚀 Starting Full Load Testing Orchestration")
        logger.info("="*80)
        
        self.is_running = True
        self.start_time = time.time()
        phase_results = []
        
        try:
            # Start system monitoring
            monitor_task = asyncio.create_task(self._system_monitoring_loop())
            self.monitoring_tasks.append(monitor_task)
            
            # Start enhanced metrics monitoring
            metrics_task = asyncio.create_task(self._enhanced_metrics_monitoring())
            self.monitoring_tasks.append(metrics_task)
            
            # Run each phase
            for i, phase in enumerate(self.phases):
                if self.should_stop:
                    logger.info("🛑 Load test stopped by user")
                    break
                
                self.current_phase = i
                logger.info(f"\\n🎯 Phase {i+1}/{len(self.phases)}: {phase.phase_name}")
                
                phase_result = await self.run_phase(phase)
                phase_results.append(phase_result)
                
                # Brief pause between phases
                if i < len(self.phases) - 1 and not self.should_stop:
                    logger.info("⏸️ Pausing 30 seconds between phases...")
                    await asyncio.sleep(30)
            
            # Wait for all remaining calls to complete
            logger.info("⏳ Waiting for remaining calls to complete...")
            timeout = 300  # 5 minutes max wait
            wait_start = time.time()
            
            while self.active_calls and (time.time() - wait_start) < timeout and not self.should_stop:
                await asyncio.sleep(10)
                logger.info(f"⏳ Waiting: {len(self.active_calls)} active calls remaining")
            
        except KeyboardInterrupt:
            logger.info("⛔ Load test interrupted by user")
        except Exception as e:
            logger.error(f"❌ Load test error: {e}")
        finally:
            # Cleanup
            self.is_running = False
            
            # Cancel monitoring tasks
            for task in self.monitoring_tasks:
                task.cancel()
            
            # Generate comprehensive report
            report = await self._generate_comprehensive_report(phase_results)
            await self._save_report(report)
            
            logger.info("🏁 Full Load Testing completed")
    
    async def _system_monitoring_loop(self):
        """Monitor system resources during load test"""
        try:
            while self.is_running and not self.should_stop:
                metrics = {
                    "timestamp": time.time(),
                    "cpu_percent": psutil.cpu_percent(interval=1),
                    "memory_percent": psutil.virtual_memory().percent,
                    "active_calls": len(self.active_calls),
                    "completed_calls": len(self.completed_calls),
                    "current_phase": self.current_phase
                }
                
                self.system_metrics.append(metrics)
                
                # Log warnings for high resource usage
                if metrics["cpu_percent"] > 85:
                    logger.warning(f"🔥 High CPU usage: {metrics['cpu_percent']:.1f}%")
                
                if metrics["memory_percent"] > 85:
                    logger.warning(f"🧠 High memory usage: {metrics['memory_percent']:.1f}%")
                
                await asyncio.sleep(30)  # Monitor every 30 seconds
                
        except asyncio.CancelledError:
            pass
    
    async def _enhanced_metrics_monitoring(self):
        """Monitor enhanced metrics from dashboard"""
        monitoring_url = f"http://localhost:{self.config.monitoring_port}"
        
        try:
            while self.is_running and not self.should_stop:
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(f"{monitoring_url}/api/enhanced-status") as resp:
                            if resp.status == 200:
                                data = await resp.json()
                                
                                # Log enhanced metrics
                                perf = data.get('performance_summary', {})
                                load_test = data.get('load_test_status', {})
                                
                                logger.info(f"📊 Enhanced Metrics: "
                                           f"Active {load_test.get('active_calls', 0)}, "
                                           f"Success {perf.get('success_rate', 0):.1f}%, "
                                           f"TTFT {perf.get('avg_ttft_seconds', 0):.3f}s")
                                
                except Exception as e:
                    logger.debug(f"Enhanced metrics monitoring error: {e}")
                
                await asyncio.sleep(60)  # Monitor every minute
                
        except asyncio.CancelledError:
            pass
    
    async def _generate_comprehensive_report(self, phase_results: List[dict]) -> LoadTestReport:
        """Generate comprehensive load test report"""
        logger.info("📋 Generating comprehensive load test report...")
        
        total_calls = len(self.completed_calls)
        successful_calls = [c for c in self.completed_calls if c.status == "completed"]
        failed_calls = [c for c in self.completed_calls if c.status in ["failed", "timeout"]]
        
        # Calculate aggregated metrics
        success_rate = (len(successful_calls) / max(1, total_calls)) * 100
        avg_duration = sum(c.duration_seconds for c in successful_calls) / max(1, len(successful_calls))
        avg_ttft = sum(c.avg_ttft for c in successful_calls if c.avg_ttft > 0) / max(1, len([c for c in successful_calls if c.avg_ttft > 0]))
        avg_user_latency = sum(c.avg_user_latency for c in successful_calls if c.avg_user_latency > 0) / max(1, len([c for c in successful_calls if c.avg_user_latency > 0]))
        total_interactions = sum(c.total_interactions for c in successful_calls)
        
        # System metrics
        peak_cpu = max((m["cpu_percent"] for m in self.system_metrics), default=0)
        peak_memory = max((m["memory_percent"] for m in self.system_metrics), default=0)
        avg_cpu = sum(m["cpu_percent"] for m in self.system_metrics) / max(1, len(self.system_metrics))
        avg_memory = sum(m["memory_percent"] for m in self.system_metrics) / max(1, len(self.system_metrics))
        
        test_duration = time.time() - self.start_time
        calls_per_minute = total_calls / (test_duration / 60)
        
        report = LoadTestReport(
            test_id=self.test_id,
            config=asdict(self.config),
            start_time=self.start_time,
            end_time=time.time(),
            total_duration_minutes=test_duration / 60,
            total_calls_attempted=total_calls,
            successful_calls=len(successful_calls),
            failed_calls=len(failed_calls),
            timeout_calls=len([c for c in failed_calls if c.status == "timeout"]),
            success_rate=success_rate,
            avg_call_duration=avg_duration,
            avg_ttft=avg_ttft,
            avg_user_latency=avg_user_latency,
            total_interactions=total_interactions,
            calls_per_minute=calls_per_minute,
            peak_cpu_percent=peak_cpu,
            peak_memory_percent=peak_memory,
            avg_cpu_percent=avg_cpu,
            avg_memory_percent=avg_memory,
            phase_results=phase_results,
            call_results=self.completed_calls
        )
        
        return report
    
    async def _save_report(self, report: LoadTestReport):
        """Save comprehensive report to files"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Save JSON report
        json_file = f"reports/load_test_report_{timestamp}.json"
        os.makedirs("reports", exist_ok=True)
        
        with open(json_file, 'w') as f:
            json.dump(asdict(report), f, indent=2, default=str)
        
        # Save CSV summary
        csv_file = f"reports/load_test_summary_{timestamp}.csv"
        
        with open(csv_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'Test ID', 'Duration (min)', 'Total Calls', 'Successful', 'Failed',
                'Success Rate (%)', 'Avg Duration (s)', 'Avg TTFT (s)', 'Avg User Latency (s)',
                'Total Interactions', 'Calls/min', 'Peak CPU (%)', 'Peak Memory (%)'
            ])
            writer.writerow([
                report.test_id, f"{report.total_duration_minutes:.1f}", report.total_calls_attempted,
                report.successful_calls, report.failed_calls, f"{report.success_rate:.1f}",
                f"{report.avg_call_duration:.1f}", f"{report.avg_ttft:.3f}", f"{report.avg_user_latency:.3f}",
                report.total_interactions, f"{report.calls_per_minute:.1f}",
                f"{report.peak_cpu_percent:.1f}", f"{report.peak_memory_percent:.1f}"
            ])
        
        # Print summary
        logger.info("="*80)
        logger.info("📋 COMPREHENSIVE LOAD TEST REPORT")
        logger.info("="*80)
        logger.info(f"🎯 Test Configuration:")
        logger.info(f"   Test ID: {report.test_id}")
        logger.info(f"   Duration: {report.total_duration_minutes:.1f} minutes")
        logger.info(f"   Phases: {len(report.phase_results)}")
        logger.info(f"   Client: {self.config.client_name}")
        logger.info("")
        logger.info(f"📊 Call Results:")
        logger.info(f"   Total calls: {report.total_calls_attempted}")
        logger.info(f"   Successful: {report.successful_calls}")
        logger.info(f"   Failed: {report.failed_calls}")
        logger.info(f"   Timeout: {report.timeout_calls}")
        logger.info(f"   Success rate: {report.success_rate:.1f}%")
        logger.info("")
        logger.info(f"⚡ Performance Metrics:")
        logger.info(f"   Average call duration: {report.avg_call_duration:.1f}s")
        logger.info(f"   Average TTFT: {report.avg_ttft:.3f}s")
        logger.info(f"   Average user latency: {report.avg_user_latency:.3f}s")
        logger.info(f"   Total interactions: {report.total_interactions}")
        logger.info(f"   Calls per minute: {report.calls_per_minute:.1f}")
        logger.info("")
        logger.info(f"💻 System Performance:")
        logger.info(f"   Peak CPU: {report.peak_cpu_percent:.1f}%")
        logger.info(f"   Peak Memory: {report.peak_memory_percent:.1f}%")
        logger.info(f"   Average CPU: {report.avg_cpu_percent:.1f}%")
        logger.info(f"   Average Memory: {report.avg_memory_percent:.1f}%")
        logger.info("")
        logger.info(f"📁 Reports saved:")
        logger.info(f"   JSON: {json_file}")
        logger.info(f"   CSV: {csv_file}")
        logger.info("="*80)

async def main():
    """Main entry point for full load testing"""
    print("🎯 Full Load Testing Orchestrator")
    print("="*50)
    
    try:
        # Create orchestrator
        orchestrator = FullLoadTestingOrchestrator()
        
        # Run full load test
        await orchestrator.run_full_load_test()
        
    except KeyboardInterrupt:
        logger.info("⛔ Load test interrupted by user")
    except Exception as e:
        logger.error(f"❌ Load test failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())