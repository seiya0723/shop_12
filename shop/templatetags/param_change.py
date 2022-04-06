from django import template

register = template.Library()


#リクエストオブジェクトのキーを指定し値を書き換える。
@register.simple_tag()
def url_replace(request, key, value):
    copied          = request.GET.copy()
    copied[key]     = value
    return copied.urlencode()





