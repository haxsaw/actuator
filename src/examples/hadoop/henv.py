from actuator.reporting import namespace_report


if __name__ == "__main__":
    from hadoop import HadoopNamespace
    hns = HadoopNamespace("VarDumpExample")
    hns.create_slaves(2)
    report = namespace_report(hns)
    for l in report:
        print(l)
