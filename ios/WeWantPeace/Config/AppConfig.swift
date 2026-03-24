import Foundation

enum AppConfig {
    static let webAppURL = URL(string: "https://www.wewantpeace.live")!
    static let apiBaseURL = URL(string: "https://api.wewantpeace.live")!

    static let productIds: Set<String> = [
        "com.wewantpeace.pro.monthly",
        "com.wewantpeace.proplus.monthly",
        "com.wewantpeace.pro.annual",
        "com.wewantpeace.proplus.annual",
        "com.wewantpeace.pro.lifetime",
        "com.wewantpeace.proplus.lifetime",
    ]

    static let bundleId = "com.wewantpeace.app"
}
