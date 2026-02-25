import { BottomNav } from "@/components/ui/bottom-nav";
import { NewEventBanner } from "@/components/ui/new-event-banner";
import { PWAInstallPrompt } from "@/components/ui/pwa-install-prompt";
import { SmartAppBanner } from "@/components/ui/smart-app-banner";

export default function MainLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <NewEventBanner />
      <main className="pb-[60px]">{children}</main>
      <BottomNav />
      <PWAInstallPrompt />
      <SmartAppBanner />
    </>
  );
}
