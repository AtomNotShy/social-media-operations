import type { TrackedProfile } from "@/src/features/tracked-profiles/types";

const sizeClasses = {
  sm: "size-10 text-xs",
  lg: "size-14 text-base",
} as const;

export function ProfileAvatar({
  profile,
  size = "sm",
}: {
  profile: Pick<TrackedProfile, "avatar_url" | "display_name">;
  size?: keyof typeof sizeClasses;
}) {
  const initials = Array.from(profile.display_name.trim())
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <span
      aria-hidden="true"
      className={`relative grid shrink-0 place-items-center overflow-hidden rounded-full bg-gradient-to-br from-primary-100 to-blue-50 font-semibold text-primary-700 ${sizeClasses[size]}`}
    >
      {initials}
      {profile.avatar_url ? (
        // Remote provider URLs are intentionally rendered with a native image so
        // each source can supply its own host without Next image configuration.
        // eslint-disable-next-line @next/next/no-img-element
        <img
          alt=""
          className="absolute inset-0 size-full object-cover"
          decoding="async"
          loading={size === "sm" ? "lazy" : "eager"}
          onError={(event) => {
            event.currentTarget.style.display = "none";
          }}
          referrerPolicy="no-referrer"
          src={profile.avatar_url}
        />
      ) : null}
    </span>
  );
}
