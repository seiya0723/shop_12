window.addEventListener("load" , function (){

    $(".url_replace").on("keydown", function(e) { if( e.keyCode === 13 ){ url_replace_send(this); } });

});
function url_replace_send(elem){

    let key     = $(elem).prop("name");
    let value   = $(elem).val();

    //TODO:ここでクエリストリングを書き換える。
    // https://maku77.github.io/js/web/search-params.html

    param   = new URLSearchParams(window.location.search);
    param.set(key, value);


    //書き換えたクエリストリングへ移動する
    // https://qiita.com/shuntaro_tamura/items/99adbe51132e0fb3c9e9
    
    window.location.href = "?" + param.toString();

}

