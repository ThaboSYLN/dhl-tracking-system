"""
Scheduler Module
Handles scheduled file processing tasks
"""
import asyncio
import logging
from datetime import datetime, time
from typing import Callable, Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)


class AutomationScheduler:
    """
    Manages scheduled automation tasks
    Default: Process files at 9 AM daily-- since we are in the dev/test process
    """
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
        logger.info("Automation Scheduler initialized")
    
    def add_daily_task(self, task: Callable, hour: int = 9, minute: int = 0, task_name: str = "daily_process"):
        """
        Add a daily scheduled task
        
        Args:
            task: Async function to execute
            hour: Hour of day (0-23)
            minute: Minute of hour (0-59)
            task_name: Name for the task
        """
        try:
            # Trigger for daily execution
            trigger = CronTrigger(hour=hour, minute=minute)
            
            self.scheduler.add_job(
                task,
                trigger=trigger,
                id=task_name,
                name=task_name,
                replace_existing=True
            )
            
            logger.info(f"Scheduled task '{task_name}' at {hour:02d}:{minute:02d} daily")
            
        except Exception as e:
            logger.error(f"Error adding scheduled task: {e}")
            raise
    
    def add_interval_task(self, task: Callable, minutes: int = 30, task_name: str = "interval_process"):
        """
        Add a task that runs at regular intervals
        
        Args:
            task: Async function to execute
            minutes: Interval in minutes
            task_name: Name for the task
        """
        try:
            self.scheduler.add_job(
                task,
                'interval',
                minutes=minutes,
                id=task_name,
                name=task_name,
                replace_existing=True
            )
            
            logger.info(f"Scheduled task '{task_name}' every {minutes} minutes")
            
        except Exception as e:
            logger.error(f"Error adding interval task: {e}")
            raise
    
    def start(self):
        """Start the scheduler"""
        if not self.is_running:
            self.scheduler.start()
            self.is_running = True
            logger.info("--> Scheduler started")
            
            # Log next run times
            jobs = self.scheduler.get_jobs()
            for job in jobs:
                logger.info(f"Next run for '{job.name}': {job.next_run_time}")
    
    def stop(self):
        """Stop the scheduler"""
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("[X]--> Scheduler stopped")
    
    def get_jobs(self):
        """Get list of scheduled jobs"""
        return self.scheduler.get_jobs()
    
    def remove_job(self, job_id: str):
        """Remove a scheduled job"""
        try:
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed job: {job_id}")
        except Exception as e:
            logger.error(f"Error removing job {job_id}: {e}")
