Download:
---------
    git clone https://github.com/joaompinto/nmon2pdf

Usage:
------
    nmon2pdf.py input_directory
    nmon2pdf.py input_directory -g10m # 10ms aggregation
    nmon2pdf.py input_directory -gh # Hourly aggregation
    nmon2pdf.py input_directory -gd # Daily aggregation (for multiple days of data)

Mandatory input directory structure:
------------------------------------
    hostname1/file1.nmon....fileN.nmon
    hostnameN/file1.nmon....fileN.nmon

Outputs:
--------
    CPU_ALL.pdf
