export default async function SimulationDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return (
    <div>
      <h1 className="text-3xl font-bold tracking-tight">
        Simulation Detail
      </h1>
      <p className="mt-2 text-muted-foreground">
        Impact dashboard for simulation {id}.
      </p>
    </div>
  );
}
