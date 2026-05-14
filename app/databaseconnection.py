import os
import logging
from typing import Optional
from supabase import create_client, Client
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SupabaseManager:
    """
    Simple and robust Supabase client connection manager
    """

    def __init__(self):
        self.supabase_url = os.getenv("SUPABASE_URL")
        self.supabase_key = os.getenv("SUPABASE_KEY")
        self.client: Optional[Client] = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize the Supabase client with basic configuration"""
        logger.info(f"Initializing Supabase client...")
        logger.info(f"SUPABASE_URL present: {bool(self.supabase_url)}")
        logger.info(f"SUPABASE_KEY present: {bool(self.supabase_key)}")

        if not self.supabase_url or not self.supabase_key:
            logger.error("❌ Missing Supabase credentials in environment variables")
            return

        try:
            # Create Supabase client with minimal configuration
            self.client = create_client(self.supabase_url, self.supabase_key)
            logger.info("✅ Supabase client created successfully")

            # Test connection with a simple query
            self._test_initial_connection()

        except Exception as e:
            logger.error(f"❌ Failed to create Supabase client: {str(e)}")
            self.client = None

    def _test_initial_connection(self) -> None:
        """Test the initial connection"""
        if not self.client:
            return

        try:
            # Try to access the profiles table
            response = self.client.table("profiles").select("id").limit(1).execute()
            logger.info("✅ Connection test successful - profiles table accessible")
        except Exception as e:
            error_msg = str(e).lower()
            if "could not find" in error_msg or "does not exist" in error_msg:
                logger.warning("⚠️ Profiles table not found - may need to be created")
            elif "row-level security" in error_msg:
                logger.info("✅ Connection successful - RLS policies active (expected)")
            else:
                logger.warning(f"⚠️ Connection test warning: {str(e)}")

    def get_client(self) -> Optional[Client]:
        """Get the Supabase client instance"""
        if not self.client:
            logger.warning("Supabase client not available, attempting to reconnect...")
            self._initialize_client()
        return self.client

    def is_connected(self) -> bool:
        """Check if Supabase client is available"""
        return self.client is not None

    def reconnect(self) -> bool:
        """Attempt to reconnect to Supabase"""
        logger.info("Attempting to reconnect to Supabase...")
        self.client = None
        self._initialize_client()
        return self.client is not None

    def health_check(self) -> bool:
        """Perform a health check on the connection"""
        if not self.client:
            return False

        try:
            # Simple connectivity test
            response = self.client.table("profiles").select("id").limit(1).execute()
            return True
        except Exception as e:
            error_msg = str(e).lower()
            if "row-level security" in error_msg:
                # RLS error means connection is working, just no access
                return True
            logger.warning(f"Health check failed: {str(e)}")
            return False

    def ensure_connection(self) -> bool:
        """Ensure we have a working connection"""
        if not self.client:
            return self.reconnect()

        if not self.health_check():
            logger.info("Health check failed, attempting reconnection...")
            return self.reconnect()

        return True

    def test_connection(self) -> dict:
        """Comprehensive connection test with detailed results"""
        if not self.client:
            if not self.reconnect():
                return {
                    "status": "error",
                    "message": "Failed to initialize Supabase client",
                    "debug": {
                        "supabase_url_present": bool(self.supabase_url),
                        "supabase_key_present": bool(self.supabase_key)
                    }
                }

        try:
            # Test profiles table access
            response = self.client.table("profiles").select("*").limit(5).execute()

            return {
                "status": "success",
                "message": "Supabase connection working - profiles table accessible",
                "existing_records": len(response.data) if response.data else 0,
                "sample_data": response.data[:2] if response.data else [],
                "table_accessible": True
            }

        except Exception as e:
            error_msg = str(e).lower()

            if "row-level security" in error_msg:
                return {
                    "status": "success",
                    "message": "Supabase connection working - RLS policies active",
                    "existing_records": 0,
                    "sample_data": [],
                    "table_accessible": True,
                    "note": "Row Level Security is protecting the data (expected behavior)"
                }
            elif "could not find" in error_msg:
                return {
                    "status": "warning",
                    "message": "Supabase connected but profiles table not found",
                    "existing_records": 0,
                    "sample_data": [],
                    "table_accessible": False,
                    "note": "Please ensure the profiles table is created"
                }
            else:
                return {
                    "status": "error",
                    "message": f"Supabase connection failed: {str(e)}",
                    "table_accessible": False
                }

# Global instance
supabase_manager = SupabaseManager()
