// src/app/register/page.tsx
import { RegisterForm } from '@/components/auth/RegisterForm';
import { MainLayout } from '@/components/layout/MainLayout';

export default function RegisterPage() {
  return (
    <MainLayout title="Register">
      <div className="py-8">
        <RegisterForm />
      </div>
    </MainLayout>
  );
}
