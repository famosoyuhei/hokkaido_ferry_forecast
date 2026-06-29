#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
自動実行テスト用スクリプト
Automation Test Script

タスクスケジューラー設定前に自動実行システムをテストする
"""

import os
import sys
import subprocess
import time
from datetime import datetime
from pathlib import Path
import logging

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('test_automation.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class AutomationTester:
    """自動実行システムテスター"""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent
        self.data_dir = self.base_dir / "data"
        self.csv_file = self.data_dir / "ferry_cancellation_log.csv"
        
    def test_environment(self):
        """環境テスト"""
        logger.info("=== Environment Test ===")
        
        # Python version check
        python_version = sys.version
        logger.info(f"Python Version: {python_version}")
        
        # Required packages check
        required_packages = ['pandas', 'requests', 'schedule', 'beautifulsoup4']
        missing_packages = []
        
        for package in required_packages:
            try:
                __import__(package)
                logger.info(f"✓ {package} is installed")
            except ImportError:
                logger.warning(f"✗ {package} is missing")
                missing_packages.append(package)
        
        if missing_packages:
            logger.info(f"Installing missing packages: {missing_packages}")
            for package in missing_packages:
                try:
                    subprocess.check_call([sys.executable, '-m', 'pip', 'install', package])
                    logger.info(f"✓ {package} installed successfully")
                except subprocess.CalledProcessError as e:
                    logger.error(f"✗ Failed to install {package}: {e}")
                    return False
        
        # Directory structure check
        if not self.data_dir.exists():
            logger.info("Creating data directory...")
            self.data_dir.mkdir(exist_ok=True)
        
        logger.info("Environment test completed successfully")
        return True
    
    def test_data_collection_single(self):
        """単発データ収集テスト"""
        logger.info("=== Single Data Collection Test ===")
        
        try:
            # Record data count before
            data_count_before = self._get_data_count()
            logger.info(f"Data count before: {data_count_before}")
            
            # Import and test monitoring system
            from ferry_monitoring_system import FerryMonitoringSystem
            
            monitor = FerryMonitoringSystem()
            logger.info("Ferry monitoring system initialized")
            
            # Test single collection
            logger.info("Testing single data collection...")
            result = monitor.collect_current_status()
            
            if result:
                logger.info("✓ Single collection test passed")
                
                # Check data count after
                time.sleep(2)  # Wait for file write
                data_count_after = self._get_data_count()
                logger.info(f"Data count after: {data_count_after}")
                
                if data_count_after > data_count_before:
                    logger.info(f"✓ New data added: {data_count_after - data_count_before} records")
                    return True
                else:
                    logger.warning("⚠ No new data was added")
                    return False
            else:
                logger.error("✗ Single collection test failed")
                return False
                
        except Exception as e:
            logger.error(f"✗ Single collection test error: {e}")
            return False
    
    def test_batch_file_execution(self):
        """バッチファイル実行テスト"""
        logger.info("=== Batch File Execution Test ===")
        
        batch_files = [
            "auto_data_collection.bat",
            "auto_data_collection_daemon.bat"
        ]
        
        for batch_file in batch_files:
            batch_path = self.base_dir / batch_file
            
            if not batch_path.exists():
                logger.error(f"✗ Batch file not found: {batch_file}")
                continue
            
            logger.info(f"Testing {batch_file}...")
            
            try:
                # Test batch file (with timeout to prevent infinite loop)
                process = subprocess.Popen(
                    [str(batch_path)],
                    cwd=str(self.base_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # Wait for 30 seconds max
                try:
                    stdout, stderr = process.communicate(timeout=30)
                    logger.info(f"✓ {batch_file} executed successfully")
                    
                    if stderr:
                        logger.warning(f"Warnings in {batch_file}: {stderr}")
                        
                except subprocess.TimeoutExpired:
                    process.kill()
                    logger.info(f"✓ {batch_file} started successfully (timeout after 30s - normal for daemon)")
                
            except Exception as e:
                logger.error(f"✗ Error executing {batch_file}: {e}")
    
    def test_data_file_access(self):
        """データファイルアクセステスト"""
        logger.info("=== Data File Access Test ===")
        
        try:
            # Test CSV file read/write
            if self.csv_file.exists():
                import pandas as pd
                df = pd.read_csv(self.csv_file, encoding='utf-8')
                logger.info(f"✓ CSV file readable: {len(df)} records")
                
                # Test write access by creating backup
                backup_file = self.csv_file.with_suffix('.backup.csv')
                df.to_csv(backup_file, index=False, encoding='utf-8')
                logger.info("✓ CSV file writable")
                
                # Clean up backup
                backup_file.unlink()
                
            else:
                logger.info("CSV file doesn't exist yet - will be created on first run")
            
            # Test log file access
            log_files = ["auto_collection.log", "daemon_collection.log", "ferry_monitoring.log"]
            
            for log_file in log_files:
                log_path = self.base_dir / log_file
                try:
                    with open(log_path, 'a', encoding='utf-8') as f:
                        f.write(f"[{datetime.now()}] Test write access\n")
                    logger.info(f"✓ Log file writable: {log_file}")
                except Exception as e:
                    logger.warning(f"⚠ Log file access issue: {log_file} - {e}")
            
            return True
            
        except Exception as e:
            logger.error(f"✗ Data file access test failed: {e}")
            return False
    
    def test_task_scheduler_readiness(self):
        """タスクスケジューラー準備確認"""
        logger.info("=== Task Scheduler Readiness Test ===")
        
        # Check if running as administrator
        try:
            import ctypes
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
            if is_admin:
                logger.info("✓ Running with administrator privileges")
            else:
                logger.warning("⚠ Not running as administrator - may need elevation for Task Scheduler")
        except:
            logger.info("⚠ Cannot determine admin status")
        
        # Check if Task Scheduler service is running
        try:
            result = subprocess.run(
                ['sc', 'query', 'Schedule'],
                capture_output=True,
                text=True
            )
            if 'RUNNING' in result.stdout:
                logger.info("✓ Task Scheduler service is running")
            else:
                logger.warning("⚠ Task Scheduler service may not be running")
        except Exception as e:
            logger.warning(f"⚠ Cannot check Task Scheduler service: {e}")
        
        # Check batch file paths
        batch_files = ["auto_data_collection.bat", "auto_data_collection_daemon.bat"]
        for batch_file in batch_files:
            full_path = self.base_dir / batch_file
            if full_path.exists():
                logger.info(f"✓ Batch file ready for Task Scheduler: {full_path}")
            else:
                logger.error(f"✗ Batch file missing: {full_path}")
        
        return True
    
    def _get_data_count(self):
        """現在のデータ件数取得"""
        try:
            if self.csv_file.exists():
                import pandas as pd
                df = pd.read_csv(self.csv_file, encoding='utf-8')
                return len(df)
            else:
                return 0
        except:
            return 0
    
    def run_all_tests(self):
        """全テスト実行"""
        logger.info("🧪 Starting Automation System Tests")
        logger.info("=" * 50)
        
        test_results = {}
        
        # Run all tests
        test_results['environment'] = self.test_environment()
        test_results['data_file_access'] = self.test_data_file_access()
        test_results['single_collection'] = self.test_data_collection_single()
        test_results['batch_execution'] = self.test_batch_file_execution()
        test_results['task_scheduler_readiness'] = self.test_task_scheduler_readiness()
        
        # Summary
        logger.info("=" * 50)
        logger.info("🏁 Test Results Summary:")
        
        all_passed = True
        for test_name, result in test_results.items():
            status = "✓ PASS" if result else "✗ FAIL"
            logger.info(f"  {test_name}: {status}")
            if not result:
                all_passed = False
        
        if all_passed:
            logger.info("🎉 All tests passed! Ready for Task Scheduler setup.")
        else:
            logger.warning("⚠ Some tests failed. Please fix issues before setting up Task Scheduler.")
        
        logger.info("\n📋 Next Steps:")
        logger.info("1. Review test results above")
        logger.info("2. Fix any failed tests")
        logger.info("3. Follow TASK_SCHEDULER_SETUP.md instructions")
        logger.info("4. Set up Windows Task Scheduler")
        
        return all_passed

def main():
    """メイン実行"""
    tester = AutomationTester()
    result = tester.run_all_tests()
    
    if result:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()