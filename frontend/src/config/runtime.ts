export function isLocalDevelopmentEnv(value: string | undefined): boolean {
  return value === "local";
}

export const localDevelopmentEnabled = isLocalDevelopmentEnv(
  process.env.NEXT_PUBLIC_APP_ENV,
);
