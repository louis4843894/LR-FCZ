import Link from "next/link";

type DataStateProps = {
  title: string;
  description: string;
};

export function DataState({ title, description }: DataStateProps) {
  return (
    <section className="data-state" role="status">
      <span className="data-state-mark" aria-hidden="true">
        i
      </span>
      <h2>{title}</h2>
      <p>{description}</p>
      <Link className="text-link" href="/">
        回到列表
      </Link>
    </section>
  );
}
