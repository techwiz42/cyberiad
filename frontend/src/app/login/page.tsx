// src/app/login/page.tsx
import { LoginForm } from '@/components/auth/LoginForm';
import { MainLayout } from '@/components/layout/MainLayout';

export default function LoginPage() {
  return (
    <MainLayout title="Login">
      <div className="py-8">
        <LoginForm />
      </div>
    </MainLayout>
  );
}

