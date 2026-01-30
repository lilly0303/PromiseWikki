/* 
   自动让外部链接在新窗口打开 
   (External links open in new tab)
*/
document.addEventListener("DOMContentLoaded", function() {
    var links = document.links;
    for (var i = 0; i < links.length; i++) {
        // 如果链接的域名和当前网站的域名不一样（说明是外链）
        if (links[i].hostname != window.location.hostname) {
            links[i].target = '_blank';
            links[i].rel = 'noopener noreferrer'; // 安全性设置
        } 
        // 这里的 else 可以留空，表示站内链接依然在当前页打开
    }
});