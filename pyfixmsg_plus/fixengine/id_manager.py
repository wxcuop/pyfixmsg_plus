import time
import asyncio

class BaseIDManager:
    """
    Base class for ID Managers that handles asynchronous ID generation and tracking.
    """
    def __init__(self, prefix="", suffix=""):
        self.prefix = prefix or f"IB{int(time.time())}"
        self.suffix = suffix
        self.counter = 0
        self.lock = asyncio.Lock()
        self.active_ids = {}  # {id: details}
        
    async def generate_new_id(self, id_type):
        """Generate a new unique ID for a given type"""
        async with self.lock:
            self.counter += 1
            timestamp = int(time.time() * 1000)
            unique_id = f"{self.prefix}-{id_type}-{timestamp}-{self.counter}{self.suffix}"
            return unique_id[:32]  # FIX typically limits ID length
    
    async def register_id(self, id, details=None):
        """Register an ID with its details"""
        async with self.lock:
            self.active_ids[id] = details or {}
            return id
    
    async def is_active(self, id):
        """Check if an ID is still active"""
        return id in self.active_ids

    async def complete_id(self, id):
        """Mark an ID as completed"""
        async with self.lock:
            if id in self.active_ids:
                self.active_ids[id]["status"] = "completed"
    
    async def reject_id(self, id):
        """Mark an ID as rejected"""
        async with self.lock:
            if id in self.active_ids:
                self.active_ids[id]["status"] = "rejected"


class OrderManager(BaseIDManager):
    """
    Manages ID generation and tracking for Orders.
    """
    async def generate_order_ids(self, details=None):
        ids = {
            "ClOrdID": await self.generate_new_id("ClOrdID"),
            "OrderID": await self.generate_new_id("OrderID"),
            "ExecID": await self.generate_new_id("ExecID"),
            "SecondaryClOrdID": await self.generate_new_id("SecondaryClOrdID"),
            "OrigClOrdID": await self.generate_new_id("OrigClOrdID")
        }
        details = details or {}
        details.update(ids)
        await self.register_id(ids["ClOrdID"], details)
        return ids


class IOIManager(BaseIDManager):
    """
    Manages ID generation and tracking for IOI (Indication of Interest) requests.
    """
    async def generate_ioi_ids(self, details=None):
        ids = {
            "IOIID": await self.generate_new_id("IOIID"),
            "IOIRefID": await self.generate_new_id("IOIRefID")
        }
        details = details or {}
        details.update(ids)
        await self.register_id(ids["IOIID"], details)
        return ids


class RFQManager(BaseIDManager):
    """
    Manages ID generation and tracking for RFQ (Request for Quote) requests.
    """
    async def generate_rfq_ids(self, details=None):
        ids = {
            "RFQReqID": await self.generate_new_id("RFQReqID")
        }
        details = details or {}
        details.update(ids)
        await self.register_id(ids["RFQReqID"], details)
        return ids


class MarketDataManager(BaseIDManager):
    """
    Manages ID generation and tracking for Market Data requests.
    """
    async def generate_market_data_ids(self, details=None):
        ids = {
            "MDReqID": await self.generate_new_id("MDReqID"),
            "MDEntryID": await self.generate_new_id("MDEntryID"),
            "MDEntryRefID": await self.generate_new_id("MDEntryRefID")
        }
        details = details or {}
        details.update(ids)
        await self.register_id(ids["MDReqID"], details)
        return ids


class SecurityManager(BaseIDManager):
    """
    Manages ID generation and tracking for Security requests.
    """
    async def generate_security_ids(self, details=None):
        ids = {
            "SecurityReqID": await self.generate_new_id("SecurityReqID"),
            "SecurityResponseID": await self.generate_new_id("SecurityResponseID"),
            "SecurityStatusReqID": await self.generate_new_id("SecurityStatusReqID"),
            "TradSesReqID": await self.generate_new_id("TradSesReqID")
        }
        details = details or {}
        details.update(ids)
        await self.register_id(ids["SecurityReqID"], details)
        return ids


class QuoteManager(BaseIDManager):
    """
    Manages ID generation and tracking for Quotes.
    """
    async def generate_quote_ids(self, details=None):
        ids = {
            "QuoteReqID": await self.generate_new_id("QuoteReqID"),
            "QuoteID": await self.generate_new_id("QuoteID"),
            "QuoteRespID": await self.generate_new_id("QuoteRespID"),
            "QuoteStatusReqID": await self.generate_new_id("QuoteStatusReqID")
        }
        details = details or {}
        details.update(ids)
        await self.register_id(ids["QuoteReqID"], details)
        return ids


class PositionManager(BaseIDManager):
    """
    Manages ID generation and tracking for Positions.
    """
    async def generate_position_ids(self, details=None):
        ids = {
            "PosReqID": await self.generate_new_id("PosReqID"),
            "PosMaintRptID": await self.generate_new_id("PosMaintRptID"),
            "PosMaintRptRefID": await self.generate_new_id("PosMaintRptRefID"),
            "PosMaintRptAckID": await self.generate_new_id("PosMaintRptAckID"),
            "PosReqType": await self.generate_new_id("PosReqType"),
            "PosReqID": await self.generate_new_id("PosReqID"),
            "PosMaintRptID": await self.generate_new_id("PosMaintRptID"),
            "PosMaintRptRefID": await self.generate_new_id("PosMaintRptRefID"),
            "PosMaintRptAckID": await self.generate_new_id("PosMaintRptAckID"),
            "PosReqType": await self.generate_new_id("PosReqType")
        }
        details = details or {}
        details.update(ids)
        await self.register_id(ids["PosReqID"], details)
        return ids


class CollateralManager(BaseIDManager):
    """
    Manages ID generation and tracking for Collateral.
    """
    async def generate_collateral_ids(self, details=None):
        ids = {
            "CollReqID": await self.generate_new_id("CollReqID"),
            "CollAsgnID": await self.generate_new_id("CollAsgnID"),
            "CollRespID": await self.generate_new_id("CollRespID"),
            "CollRptID": await self.generate_new_id("CollRptID"),
            "CollInquiryID": await self.generate_new_id("CollInquiryID")
        }
        details = details or {}
        details.update(ids)
        await self.register_id(ids["CollReqID"], details)
        return ids


class UserManager(BaseIDManager):
    """
    Manages ID generation and tracking for User requests.
    """
    async def generate_user_ids(self, details=None):
        ids = {
            "UserRequestID": await self.generate_new_id("UserRequestID"),
            "UserResponseID": await self.generate_new_id("UserResponseID")
        }
        details = details or {}
        details.update(ids)
        await self.register_id(ids["UserRequestID"], details)
        return ids


# Additional managers can be defined similarly for other request types
