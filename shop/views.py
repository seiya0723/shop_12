from django.shortcuts import render,redirect


from django.contrib.auth.mixins import LoginRequiredMixin

#from django.views import View
from rest_framework.views import APIView as View

from django.http.response import JsonResponse
from django.template.loader import render_to_string

from django.db.models import Q
from django.core.paginator import Paginator

from .models import Product,Cart,Address,Order
from .forms import ( CartForm,ProductSortForm,AddressForm,OrderDetailForm,
                     OrderBeforeForm,OrderSessionForm,OrderCheckoutSuccessForm,
                     ProductMaxPriceForm,ProductMinPriceForm,
                     
                     )



import stripe
from django.urls import reverse_lazy
from django.conf import settings
from django.utils import timezone



class IndexView(View):

    def get(self, request, *args, **kwargs):

        context             = {}

        #並び替え用のフォーム
        context["choices"]  = [ { "value":choice[0], "label":choice[1] }  for choice in ProductSortForm.choices ]

        form        = ProductSortForm(request.GET)
        order_by    = ""

        #並び替えが指定されている場合。(後に検索をするのであれば、変数order_byに並び替えする値を格納)
        if form.is_valid():
            cleaned             = form.clean()
            order_by            = cleaned["order_by"]


        #TODO:ここで検索をする。(価格帯、商品カテゴリ、)

        #クエリを初期化しておく。
        query   = Q()

        if "search" in request.GET:

            #(2)全角スペースを半角スペースに変換、スペース区切りでリストにする。
            words   = request.GET["search"].replace("　"," ").split(" ")

            #(3)クエリを追加する
            for word in words:

                #空欄の場合は次のループへ
                if word == "":
                    continue

                #TIPS:AND検索の場合は&を、OR検索の場合は|を使用する。
                query &= Q(name__contains=word)


        #TODO:金額の上限
        form        = ProductMaxPriceForm(request.GET)
        
        if form.is_valid():
            cleaned = form.clean()
            query &= Q(price__lte=cleaned["max_price"])


        #TODO:金額の下限
        form        = ProductMinPriceForm(request.GET)

        if form.is_valid():
            cleaned = form.clean()
            query &= Q(price__gte=cleaned["min_price"])


        if order_by:
            products    = Product.objects.filter(query).order_by(order_by)
        else:
            products    = Product.objects.filter(query).order_by("-dt")

        paginator       = Paginator(products,2)


        if "page" in request.GET:
            context["products"]     = paginator.get_page(request.GET["page"])
        else:
            context["products"]     = paginator.get_page(1)

        
        return render(request, "shop/index.html", context)

index   = IndexView.as_view()


class ProductView(LoginRequiredMixin,View):

    def get(self, request, pk, *args, **kwargs):
        #TODO:ここに商品の個別ページを作る

        product = Product.objects.filter(id=pk).first()

        if not product:
            return redirect("shop:index")

        context = {}
        context["product"]  = product

        return render(request, "shop/product.html", context)


    def post(self, request, pk, *args, **kwargs):
        #ここでユーザーのカートへ追加
        if request.user.is_authenticated:

            copied  = request.POST.copy()

            copied["user"]      = request.user.id
            copied["product"]   = pk

            form    = CartForm(copied)

            if not form.is_valid():
                print("バリデーションNG")
                return redirect("shop:index")


            print("バリデーションOK")

            #TIPS:ここで既に同じ商品がカートに入っている場合、レコード新規作成ではなく、既存レコードにamount分だけ追加する。
            cart    = Cart.objects.filter(user=request.user.id, product=pk).first()

            if cart:
                cleaned = form.clean()

                #TODO:ここでカートに数量を追加する時、追加される数量が在庫数を上回っていないかチェックする。上回る場合は拒否する。
                if cart.amount_change(cart.amount + cleaned["amount"]):
                    cart.amount += cleaned["amount"]
                    cart.save()
                else:
                    print("在庫数を超過しているため、カートに追加できません。")

            else:          
                #存在しない場合は新規作成
                form.save()

        else:
            print("未認証です")
            #TODO:未認証ユーザーにはCookieにカートのデータを格納するのも良い

        return redirect("shop:index")

product = ProductView.as_view()



#pkは、GETとPOSTの場合は商品ID、PUTとDELETEの場合はレビューID
class ProductCommentView(LoginRequiredMixin,View):

    def get(self, request, pk, *args, **kwargs):
        #TODO:ここで利用者から投稿されたレビューをページネーションで閲覧できるようにする。
        pass

    def post(self, request, pk, *args, **kwargs):
        #TODO:ここで利用者から投稿されたレビューをDBに格納。
        pass

    def put(self, request, pk, *args, **kwargs):
        #TODO:ここで利用者から投稿されたレビューを編集する
        pass

    def delete(self, request, pk, *args, **kwargs):
        #TODO:ここで利用者から投稿されたレビューを削除する
        pass

product_comment = ProductCommentView.as_view()


class AddressView(LoginRequiredMixin,View):

    def get(self, request, *args, **kwargs):

        context                 = {}
        context["addresses"]    = Address.objects.filter(user=request.user.id).order_by("-dt")

        return render(request,"shop/address.html",context)

    def post(self, request, *args, **kwargs):

        copied          = request.POST.copy()
        copied["user"]  = request.user.id

        form    = AddressForm(copied)

        if form.is_valid():
            print("バリデーションOK")
            form.save()

        return redirect("shop:address")

address = AddressView.as_view()


class CartView(LoginRequiredMixin,View):

    def get_context(self, request):
        #ここでカートの中身を表示
        context = {}
        carts   = Cart.objects.filter(user=request.user.id)

        context["total"]    = 0
        for cart in carts:
            context["total"] += cart.total()

        context["carts"]    = carts
        
        return context


    def get(self, request, *args, **kwargs):
        context = self.get_context(request)

        return render(request, "shop/cart.html", context)


    def put(self, request, *args, **kwargs):
        #ここでカートの数量変更を受け付ける。
        
        data    = { "error":True }
        
        if "pk" not in kwargs:
            return JsonResponse(data)
        
        #リクエストがあったカートモデルのidとリクエストしてきたユーザーのidで検索する
        #(ユーザーで絞り込まない場合。第三者のカート内数量を勝手に変更されるため。)
        cart    = Cart.objects.filter(id=kwargs["pk"],user=request.user.id).first()

        if not cart:
            return JsonResponse(data)

        copied          = request.data.copy()
        copied["user"]  = request.user.id
        

        #編集対象を特定して数量を変更させる。
        form    = CartForm(copied,instance=cart)

        if not form.is_valid():
            print("バリデーションNG")
            print(form.errors)
            return JsonResponse(data)


        print("バリデーションOK")

        cleaned = form.clean()

        if not cart.amount_change(cleaned["amount"]):
            print("数量が在庫数を超過。")
            return JsonResponse(data)

        #数量が規定値であれば編集
        form.save()

        context         = self.get_context(request)
        data["content"] = render_to_string("shop/cart_content.html", context, request)
        data["error"]   = False

        return JsonResponse(data)

    def delete(self, request, *args, **kwargs):
        data    = {"error":True}

        if "pk" not in kwargs:
            return JsonResponse(data)

        cart    = Cart.objects.filter(id=kwargs["pk"],user=request.user.id).first()

        if not cart:
            return JsonResponse(data)

        cart.delete()

        context         = self.get_context(request)
        data["content"] = render_to_string("shop/cart_content.html", context, request)
        data["error"]   = False

        return JsonResponse(data)


cart = CartView.as_view()


#Orderモデルを作る(配送先の住所など必要な情報を記録する。)
class CheckoutBeforeView(LoginRequiredMixin,View):

    def get(self, request, *args, **kwargs):

        context                 = {}

        #配送先の住所の選択肢を表示
        context["addresses"]    = Address.objects.filter(user=request.user.id).order_by("-dt")


        return render(request,"shop/checkout_before.html",context)

    def post(self, request, *args, **kwargs):

        #Orderモデルを作る

        copied          = request.POST.copy()
        copied["user"]  = request.user.id

        form    = OrderBeforeForm(copied)

        if not form.is_valid():
            print("バリデーションNG")
            return redirect("shop:checkout_before")


        print("バリデーションOK")
        order   = form.save()
        

        #決済ページへリダイレクトする。
        return redirect("shop:checkout", order.id)

checkout_before = CheckoutBeforeView.as_view()


#決済ページ
class CheckoutView(LoginRequiredMixin,View):

    def get(self, request, pk, *args, **kwargs):

        context = {}

        #セッションを開始するため、秘密鍵をセットする。
        stripe.api_key = settings.STRIPE_API_KEY

        #カート内の商品情報を取得、Stripeのセッション作成に使う。
        carts   = Cart.objects.filter(user=request.user.id)

        items   = []
        for cart in carts:
            items.append( {'price_data': { 'currency': 'jpy', 'product_data': { 'name': cart.product.name }, 'unit_amount': cart.product.price }, 'quantity': cart.amount } ) 

        session = stripe.checkout.Session.create(
                payment_method_types=['card'],

                #顧客が購入する商品
                line_items=items,

                mode='payment',

                #決済成功した後のリダイレクト先()
                #TIPS:pkを使う時、reverse_lazyでは通用しない?
                success_url=request.build_absolute_uri(reverse_lazy("shop:checkout_success", kwargs={"pk":pk} )) + "?session_id={CHECKOUT_SESSION_ID}",

                #決済キャンセルしたときのリダイレクト先
                cancel_url=request.build_absolute_uri(reverse_lazy("shop:checkout_error")),
                )


        print(session)

        #この公開鍵を使ってテンプレート上のJavaScriptにセットする。顧客が入力する情報を暗号化させるための物
        context["public_key"]   = settings.STRIPE_PUBLISHABLE_KEY

        #このStripeのセッションIDをテンプレート上のJavaScriptにセットする。上記のビューで作ったセッションを顧客に渡して決済させるための物
        context["session_id"]   = session["id"]


        #ここでOrderに記録
        order   = Order.objects.filter(id=pk,user=request.user.id).first()

        if not order:
            return redirect("shop:checkout_before")

        form    = OrderSessionForm({"session_id":session["id"]},instance=order)

        if not form.is_valid():
            print("バリデーションNG")
            return redirect("shop:checkout_before")

        print("バリデーションOK")
        form.save()


        #ここでOrderDetailに記録

        carts   = Cart.objects.filter(user=request.user.id)

        data    = {}

        for cart in carts:

            data["order"]           = pk
            data["user"]            = request.user.id
            data["product_price"]   = cart.product.price
            data["product_name"]    = cart.product.name
            data["amount"]          = cart.amount
 
            form    = OrderDetailForm(data)

            if form.is_valid():
                form.save()



        return render(request, "shop/checkout.html", context)

checkout    = CheckoutView.as_view()

#決済成功ページ
class CheckoutSuccessView(LoginRequiredMixin,View):

    def get(self, request, pk, *args, **kwargs):

        #セッションIDがパラメータに存在するかチェック。なければエラー画面へ
        if "session_id" not in request.GET:
            return redirect("shop:checkout_error")

        #ここでセッションの存在チェック(存在しないセッションIDを適当に入力した場合、ここでエラーが出る。)
        #1度でもここを通ると、exceptになる。(決済成功した後更新ボタンを押すと、例外が発生。)
        try:
            session     = stripe.checkout.Session.retrieve(request.GET["session_id"])
            print(session)
        except Exception as e:
            print(e)
            return redirect("shop:checkout_error")


        #ここで決済完了かどうかチェックできる。(何らかの方法でセッションIDを取得し、URLに直入力した場合、ここでエラーが出る。)
        try:
            customer    = stripe.Customer.retrieve(session.customer)
            print(customer)
        except:
            return redirect("shop:checkout_error")


        context = {}

        #ここでOrderモデルへ決済時刻の記録を行う。
        order   = Order.objects.filter(id=pk,user=request.user.id).first()

        if not order:
            return redirect("shop:checkout_before")

        form    = OrderCheckoutSuccessForm({ "paid":timezone.now() },instance=order)

        if not form.is_valid():
            return redirect("shop:checkout_before")

        print("バリデーションOK")
        form.save()

        #カートの中身を削除する
        carts   = Cart.objects.filter(user=request.user.id)
        carts.delete()


        #TODO:決済を受け付けたので、管理者にメールで配送の催促をするのも良いかと

        return render(request, "shop/checkout_success.html", context)

checkout_success    = CheckoutSuccessView.as_view()

#決済失敗ページ
class CheckoutErrorView(LoginRequiredMixin,View):

    def get(self, request, *args, **kwargs):

        context = {}

        return render(request, "shop/checkout_error.html", context)


checkout_error    = CheckoutErrorView.as_view()



