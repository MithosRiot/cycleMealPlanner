from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, event
from sqlalchemy.orm import Mapped, Session, mapped_column, relationship
from app.database.base import Base

class ShoppingList(Base):
    __tablename__="shopping_lists"
    id:Mapped[int]=mapped_column(Integer,primary_key=True); household_id:Mapped[int]=mapped_column(ForeignKey("households.id",ondelete="CASCADE"),nullable=False); meal_cycle_id:Mapped[int]=mapped_column(ForeignKey("meal_cycles.id",ondelete="CASCADE"),nullable=False,unique=True); generated_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,default=datetime.utcnow)
    items:Mapped[list[ShoppingListItem]]=relationship(back_populates="shopping_list",cascade="all, delete-orphan",order_by="ShoppingListItem.id")

class ShoppingListItem(Base):
    __tablename__="shopping_list_items"
    id:Mapped[int]=mapped_column(Integer,primary_key=True); shopping_list_id:Mapped[int]=mapped_column(ForeignKey("shopping_lists.id",ondelete="CASCADE"),nullable=False); ingredient_id:Mapped[int]=mapped_column(ForeignKey("ingredients.id",ondelete="RESTRICT"),nullable=False); shopping_category_id:Mapped[int|None]=mapped_column(ForeignKey("shopping_categories.id",ondelete="SET NULL")); unit_id:Mapped[int]=mapped_column(ForeignKey("measurement_units.id",ondelete="RESTRICT"),nullable=False); unit_family:Mapped[str]=mapped_column(String(20),nullable=False); required_quantity:Mapped[Decimal]=mapped_column(Numeric(16,6),nullable=False); inventory_quantity:Mapped[Decimal]=mapped_column(Numeric(16,6),nullable=False); generated_quantity:Mapped[Decimal]=mapped_column(Numeric(16,6),nullable=False); adjustment_quantity:Mapped[Decimal]=mapped_column(Numeric(16,6),nullable=False,default=Decimal("0")); source_trace:Mapped[str]=mapped_column(Text,nullable=False,default="[]"); warning:Mapped[str|None]=mapped_column(Text); status:Mapped[str]=mapped_column(String(20),nullable=False,default="PENDING"); actual_quantity:Mapped[Decimal|None]=mapped_column(Numeric(16,6)); actual_unit_id:Mapped[int|None]=mapped_column(ForeignKey("measurement_units.id",ondelete="RESTRICT")); purchase_date:Mapped[date|None]=mapped_column(Date); storage_location_id:Mapped[int|None]=mapped_column(ForeignKey("inventory_locations.id",ondelete="RESTRICT")); expiration_date:Mapped[date|None]=mapped_column(Date); purchase_notes:Mapped[str|None]=mapped_column(Text); inventory_lot_id:Mapped[int|None]=mapped_column(ForeignKey("inventory_lots.id",ondelete="RESTRICT"),unique=True); completed_at:Mapped[datetime|None]=mapped_column(DateTime); baseline_required_quantity:Mapped[Decimal|None]=mapped_column(Numeric(16,6)); plan_delta_quantity:Mapped[Decimal]=mapped_column(Numeric(16,6),nullable=False,default=Decimal("0")); purchased_excess_quantity:Mapped[Decimal]=mapped_column(Numeric(16,6),nullable=False,default=Decimal("0"))
    shopping_list:Mapped[ShoppingList]=relationship(back_populates="items"); purchases:Mapped[list[ShoppingItemPurchase]]=relationship(back_populates="shopping_item",cascade="all, delete-orphan",order_by="ShoppingItemPurchase.id")
    __table_args__=(UniqueConstraint("shopping_list_id","ingredient_id","unit_family",name="uq_shopping_item_ingredient_family"),)

class ShoppingItemPurchase(Base):
    __tablename__="shopping_item_purchases"
    id:Mapped[int]=mapped_column(Integer,primary_key=True); shopping_list_item_id:Mapped[int]=mapped_column(ForeignKey("shopping_list_items.id",ondelete="CASCADE"),nullable=False,index=True); actual_quantity:Mapped[Decimal]=mapped_column(Numeric(16,6),nullable=False); actual_unit_id:Mapped[int]=mapped_column(ForeignKey("measurement_units.id",ondelete="RESTRICT"),nullable=False); purchased_ingredient_id:Mapped[int|None]=mapped_column(Integer); satisfied_quantity:Mapped[Decimal|None]=mapped_column(Numeric(16,6)); satisfied_unit_id:Mapped[int|None]=mapped_column(Integer); purchase_kind:Mapped[str]=mapped_column(String(20),nullable=False,default="STANDARD"); idempotency_key:Mapped[str|None]=mapped_column(String(64),unique=True); purchase_date:Mapped[date|None]=mapped_column(Date); storage_location_id:Mapped[int]=mapped_column(ForeignKey("inventory_locations.id",ondelete="RESTRICT"),nullable=False); expiration_date:Mapped[date|None]=mapped_column(Date); purchase_notes:Mapped[str|None]=mapped_column(Text); inventory_lot_id:Mapped[int]=mapped_column(ForeignKey("inventory_lots.id",ondelete="RESTRICT"),nullable=False,unique=True); completed_at:Mapped[datetime]=mapped_column(DateTime,nullable=False,default=datetime.utcnow)
    shopping_item:Mapped[ShoppingListItem]=relationship(back_populates="purchases")

@event.listens_for(Session,"before_flush")
def _attach_new_shopping_purchases(session:Session,_flush_context,_instances)->None:
    for purchase in tuple(session.new):
        if not isinstance(purchase,ShoppingItemPurchase) or purchase.shopping_item is not None: continue
        item=session.get(ShoppingListItem,purchase.shopping_list_item_id)
        if item is not None and purchase not in item.purchases: item.purchases.append(purchase)
