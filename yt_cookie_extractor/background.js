chrome.cookies.getAll({ domain: "youtube.com" }, function(cookies) {
    let cookieString = cookies.map(c => c.name + "=" + c.value).join("; ");

    fetch("http://127.0.0.1:5000/receive-cookies", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cookies: cookieString })
    }).then(response => response.json()).then(data => console.log("Sent:", data));
});
