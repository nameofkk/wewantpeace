import SwiftUI

struct ContentView: View {
    var body: some View {
        WebViewRepresentable()
            .ignoresSafeArea(.container, edges: .bottom)
    }
}

struct WebViewRepresentable: UIViewControllerRepresentable {
    func makeUIViewController(context: Context) -> WebViewController {
        return WebViewController()
    }

    func updateUIViewController(_ uiViewController: WebViewController, context: Context) {}
}
