import { GalleryVerticalEnd } from "lucide-react";
import Link from "next/link";

export function AuthShell({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <main className="grid min-h-screen lg:grid-cols-[minmax(360px,0.8fr)_1.2fr]">
      <section className="flex flex-col justify-between bg-text p-8 text-white sm:p-12 lg:p-16">
        <Link className="flex items-center gap-3" href="/">
          <span className="grid size-10 place-items-center rounded-xl bg-white text-text">
            <GalleryVerticalEnd aria-hidden="true" size={19} />
          </span>
          <span>
            <span className="block text-sm font-semibold">序章</span>
            <span className="block text-[10px] tracking-[0.16em] text-white/55">
              SOCIAL OPS
            </span>
          </span>
        </Link>

        <div className="my-16 max-w-lg">
          <p className="text-xs font-semibold tracking-[0.18em] text-blue-300 uppercase">
            {eyebrow}
          </p>
          <h1 className="mt-4 text-3xl font-semibold tracking-tight sm:text-4xl">
            {title}
          </h1>
          <p className="mt-4 text-sm leading-7 text-white/65">{description}</p>
        </div>

        <p className="text-xs leading-5 text-white/40">
          身份与工作区数据由受控服务处理，浏览器不会读取第三方供应商密钥。
        </p>
      </section>
      <section className="flex items-center justify-center bg-canvas px-5 py-12 sm:px-10">
        <div className="w-full max-w-md">{children}</div>
      </section>
    </main>
  );
}
