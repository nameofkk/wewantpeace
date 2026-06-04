import Foundation
import StoreKit

@MainActor
class StoreManager: ObservableObject {
    static let shared = StoreManager()

    @Published var products: [Product] = []
    @Published var purchasedProductIDs: Set<String> = []

    private var updateListenerTask: Task<Void, Error>?

    init() {
        updateListenerTask = listenForTransactions()
        Task { await loadProducts() }
    }

    deinit {
        updateListenerTask?.cancel()
    }

    // MARK: - 상품 로드

    func loadProducts() async {
        do {
            products = try await Product.products(for: AppConfig.productIds)
                .sorted { $0.price < $1.price }
        } catch {
            print("[StoreManager] 상품 로드 실패: \(error)")
        }
    }

    // MARK: - 구매

    func purchase(_ product: Product) async throws -> Transaction? {
        let result = try await product.purchase()

        switch result {
        case .success(let verification):
            let transaction = try checkVerified(verification)
            // 백엔드 검증은 WebView 브릿지에서 처리
            await transaction.finish()
            purchasedProductIDs.insert(product.id)
            return transaction

        case .userCancelled:
            return nil

        case .pending:
            return nil

        @unknown default:
            return nil
        }
    }

    // MARK: - 구매 복원

    func restorePurchases() async -> [Transaction] {
        var restored: [Transaction] = []
        for await result in Transaction.currentEntitlements {
            if let transaction = try? checkVerified(result) {
                restored.append(transaction)
                purchasedProductIDs.insert(transaction.productID)
            }
        }
        return restored
    }

    // MARK: - 거래 리스너

    private func listenForTransactions() -> Task<Void, Error> {
        return Task.detached { [weak self] in
            for await result in Transaction.updates {
                guard let self = self else { return }
                if let transaction = try? await self.checkVerified(result) {
                    await transaction.finish()
                    await MainActor.run {
                        self.purchasedProductIDs.insert(transaction.productID)
                    }
                }
            }
        }
    }

    // MARK: - 검증

    private func checkVerified<T>(_ result: VerificationResult<T>) throws -> T {
        switch result {
        case .unverified(_, let error):
            throw error
        case .verified(let item):
            return item
        }
    }
}
