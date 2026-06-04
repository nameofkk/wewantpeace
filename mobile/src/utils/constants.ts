export const WEB_URL = "https://www.wewantpeace.live";
export const API_BASE = "https://api.wewantpeace.live";

// FCM Notification Channels (Android)
export const CHANNEL_ALERTS = "wwp_alerts";
export const CHANNEL_CRITICAL = "wwp_critical";

// Google Play IAP product IDs
export const GOOGLE_PRODUCT_IDS: Record<string, string> = {
  pro: "com.wewantpeace.pro_monthly",
  pro_plus: "com.wewantpeace.proplus_monthly",
  pro_annual: "com.wewantpeace.pro_annual",
  pro_plus_annual: "com.wewantpeace.proplus_annual",
  pro_lifetime: "com.wewantpeace.pro_lifetime",
  pro_plus_lifetime: "com.wewantpeace.proplus_lifetime",
};

// Apple IAP product IDs
export const APPLE_PRODUCT_IDS: Record<string, string> = {
  pro: "com.wewantpeace.pro.monthly",
  pro_plus: "com.wewantpeace.proplus.monthly",
  pro_annual: "com.wewantpeace.pro.annual",
  pro_plus_annual: "com.wewantpeace.proplus.annual",
  pro_lifetime: "com.wewantpeace.pro.lifetime",
  pro_plus_lifetime: "com.wewantpeace.proplus.lifetime",
};
