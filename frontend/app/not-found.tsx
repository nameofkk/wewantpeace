import Link from "next/link";
import { Home, AlertTriangle } from "lucide-react";

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen px-6 text-center">
      <AlertTriangle className="h-16 w-16 text-muted-foreground mb-4" />
      <h1 className="text-4xl font-bold mb-2">404</h1>
      <p className="text-lg font-medium mb-1">페이지를 찾을 수 없습니다</p>
      <p className="text-sm text-muted-foreground mb-8">
        요청하신 페이지가 존재하지 않거나 이동되었습니다.
      </p>
      <Link
        href="/"
        className="flex items-center gap-2 rounded-xl bg-primary px-6 py-3 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
      >
        <Home className="h-4 w-4" />
        홈으로 돌아가기
      </Link>
    </div>
  );
}
