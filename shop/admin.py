from django.contrib import admin

from .models import Product,Cart,Address,Order,OrderDetail


class OrderAdmin(admin.ModelAdmin):

    list_display    = ["dt","user","prefecture","city","address","paid","deliverd","session_id",]

class OrderDetailAdmin(admin.ModelAdmin):

    list_display    = ["order","user","product_price","product_name","amount",]



admin.site.register(Product)
admin.site.register(Cart)
admin.site.register(Address)

admin.site.register(Order,OrderAdmin)
admin.site.register(OrderDetail,OrderDetailAdmin)

