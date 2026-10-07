/* ARAB STORE Web Push service worker */
self.addEventListener("push", (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch (_) {}
  const title = data.title || "إشعار جديد";
  const options = {
    body: data.message || "لديك تحديث جديد في المتجر",
    icon: "/site-icon",
    badge: "/site-icon",
    tag: "arab-store-notification",
    renotify: true,
    data: { url: "/activity.html" },
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const target = (event.notification.data && event.notification.data.url) || "/activity.html";
  event.waitUntil(
    clients.matchAll({ type: "window", includeUncontrolled: true }).then((list) => {
      for (const client of list) {
        if ("focus" in client) return client.focus();
      }
      return clients.openWindow(target);
    })
  );
});
