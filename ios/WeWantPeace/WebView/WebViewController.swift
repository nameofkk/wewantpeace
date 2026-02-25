import UIKit
import WebKit
import StoreKit

class WebViewController: UIViewController, WKNavigationDelegate, WKScriptMessageHandler {
    private var webView: WKWebView!
    private let storeManager = StoreManager.shared

    override func viewDidLoad() {
        super.viewDidLoad()
        setupWebView()
        loadWebApp()
    }

    // MARK: - WebView 설정

    private func setupWebView() {
        let config = WKWebViewConfiguration()
        let contentController = config.userContentController

        // JS 브릿지 핸들러 등록
        contentController.add(self, name: "storekit")

        // iOS 앱 감지용 스크립트 주입
        let script = WKUserScript(
            source: "window.__IOS_APP__ = true;",
            injectionTime: .atDocumentStart,
            forMainFrameOnly: false
        )
        contentController.addUserScript(script)

        // 웹앱 설정
        config.allowsInlineMediaPlayback = true
        config.mediaTypesRequiringUserActionForPlayback = []

        webView = WKWebView(frame: view.bounds, configuration: config)
        webView.autoresizingMask = [.flexibleWidth, .flexibleHeight]
        webView.navigationDelegate = self
        webView.allowsBackForwardNavigationGestures = true
        webView.scrollView.contentInsetAdjustmentBehavior = .always

        // Safe area 대응
        if #available(iOS 15.0, *) {
            webView.underPageBackgroundColor = UIColor(red: 0.1, green: 0.1, blue: 0.18, alpha: 1)
        }

        view.addSubview(webView)
    }

    private func loadWebApp() {
        let request = URLRequest(url: AppConfig.webAppURL)
        webView.load(request)
    }

    // MARK: - WKScriptMessageHandler

    func userContentController(
        _ userContentController: WKUserContentController,
        didReceive message: WKScriptMessage
    ) {
        guard message.name == "storekit",
              let body = message.body as? [String: Any],
              let action = body["action"] as? String else {
            return
        }

        switch action {
        case "purchase":
            guard let productId = body["productId"] as? String else { return }
            handlePurchase(productId: productId)

        case "restore":
            handleRestore()

        case "getProducts":
            handleGetProducts()

        default:
            break
        }
    }

    // MARK: - StoreKit 액션

    private func handlePurchase(productId: String) {
        Task { @MainActor in
            guard let product = storeManager.products.first(where: { $0.id == productId }) else {
                sendStoreKitResult([
                    "action": "purchase",
                    "success": false,
                    "error": "Product not found",
                ])
                return
            }

            do {
                if let transaction = try await storeManager.purchase(product) {
                    sendStoreKitResult([
                        "action": "purchase",
                        "success": true,
                        "transactionId": String(transaction.id),
                        "originalTransactionId": String(transaction.originalID),
                        "productId": transaction.productID,
                    ])
                } else {
                    // 사용자 취소 또는 대기 중
                    sendStoreKitResult([
                        "action": "purchase",
                        "success": false,
                        "cancelled": true,
                    ])
                }
            } catch {
                sendStoreKitResult([
                    "action": "purchase",
                    "success": false,
                    "error": error.localizedDescription,
                ])
            }
        }
    }

    private func handleRestore() {
        Task { @MainActor in
            let transactions = await storeManager.restorePurchases()
            let items = transactions.map { tx -> [String: Any] in
                return [
                    "transactionId": String(tx.id),
                    "originalTransactionId": String(tx.originalID),
                    "productId": tx.productID,
                ]
            }
            sendStoreKitResult([
                "action": "restore",
                "success": true,
                "transactions": items,
            ])
        }
    }

    private func handleGetProducts() {
        Task { @MainActor in
            await storeManager.loadProducts()
            let items = storeManager.products.map { p -> [String: Any] in
                return [
                    "id": p.id,
                    "displayName": p.displayName,
                    "description": p.description,
                    "price": p.price.description,
                    "displayPrice": p.displayPrice,
                ]
            }
            sendStoreKitResult([
                "action": "getProducts",
                "success": true,
                "products": items,
            ])
        }
    }

    // MARK: - 웹으로 결과 전송

    private func sendStoreKitResult(_ result: [String: Any]) {
        guard let data = try? JSONSerialization.data(withJSONObject: result),
              let jsonString = String(data: data, encoding: .utf8) else {
            return
        }
        let js = "window.handleStoreKitResult && window.handleStoreKitResult(\(jsonString));"
        webView.evaluateJavaScript(js)
    }

    // MARK: - WKNavigationDelegate

    func webView(
        _ webView: WKWebView,
        decidePolicyFor navigationAction: WKNavigationAction,
        decisionHandler: @escaping (WKNavigationActionPolicy) -> Void
    ) {
        guard let url = navigationAction.request.url else {
            decisionHandler(.allow)
            return
        }

        // 외부 링크는 Safari에서 열기
        if url.host != AppConfig.webAppURL.host {
            UIApplication.shared.open(url)
            decisionHandler(.cancel)
            return
        }

        decisionHandler(.allow)
    }
}
