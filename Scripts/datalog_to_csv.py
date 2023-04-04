import json
# Convert logged .data to csv format


delim = ","


def main():
    filename = input("logfile to read: ")
    lines = []
    with open(filename, "r") as file:
        lines = file.readlines()
    csv = [
        [delim.join(["!TABLE", "Default values"])],
        get_default_lines(lines[0]),
        ["!ENDTABLE"],
        [delim.join(["!TABLE", "Config"])],
        get_conf_lines(lines[1]),
        ["!ENDTABLE"],
        [delim.join(["!TABLE", "Results"])],
        get_result_lines(lines[2:]),
        ["!ENDTABLE"]
    ]
    csvfilename = filename.split(".")[0] + ".csv"
    with open(csvfilename, "w") as file:
        for table in csv:
            for line in table:
                file.write(line + "\n")


def get_default_lines(jsonline):
    c = json.loads(jsonline)
    header = list(c[0].keys())
    values = []
    for key in header:
        if key == "results":
            for a in c[0]["results"].keys():
                for v in c[0]["results"][a].keys():
                    header.append(a + " " + v)
    for case in c:
        cval = []
        for key in header:
            if key == "results":
                cval.append(str(len(case["results"].keys())))
                for a in case["results"].keys():
                    for v in case["results"][a].keys():
                        cval.append(str(case["results"][a][v]))
            else:
                if key in case.keys():
                    cval.append(str(case[key]))
        values.append(cval)
    csvpart = [delim.join(header)]
    for val in values:
        csvpart.append(delim.join(val))
    return csvpart


def get_conf_lines(jsonline):
    c = json.loads(jsonline)
    header = c.keys()
    values = []
    for key in header:
        values.append(str(c[key]))
    return [delim.join(header), delim.join(values)]


def get_result_lines(jsonlines):
    lines = []
    for line in jsonlines:
        lines.append(json.loads(line))

    header = ["generic"]
    header2 = ["timestamp"]
    values = []
    h = lines[0]
    for i, line in enumerate(lines):
        values.append([line["timestamp"]])
    for rail in h["power"].keys():
        for stat in h["power"][rail].keys():
            header.append(rail)
            header2.append(stat)
            for i, line in enumerate(lines):
                values[i].append(str(line["power"][rail][stat]))

    for r, res in enumerate(h["results"]):
        for key in res.keys():
            if key != "Algorithm" and key != "testcase":
                header.append(f'{res["Algorithm"]} #{res["testcase"]}')
                header2.append(key)
                for i, line in enumerate(lines):
                    values[i].append(str(line["results"][r][key]))

    csvpart = [delim.join(header), delim.join(header2)]
    for line in values:
        csvpart.append(delim.join(line))
    return csvpart


if __name__ == '__main__':
    main()
