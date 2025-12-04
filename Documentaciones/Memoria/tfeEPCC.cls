\NeedsTeXFormat{LaTeX2e}[2021/11/15]
\ProvidesClass{tfeEPCC}[2025/01/18 v1.0 LaTeX document class for Bachelor or Master's Theses in the School of Technology of Cáceres (UEx)]

\LoadClass[12pt,a4paper,oneside]{book}

\RequirePackage{etoolbox}
\RequirePackage{appendix}
\RequirePackage[nohints]{minitoc}
\RequirePackage{hyperref}

%% Add automatic toc to every chapter
\DeclareOption{minitoc}{%
    \dominitoc%
    \patchcmd{\@makechapterhead}% <cmd>
    {40\p@}% <search>
    {40\p@\minitoc}% <replace>
    {}{}% <success><failure>
    \let\oldappendix\appendix%
    \renewcommand{\appendix}{\oldappendix\adjustmtc}%
}

% Remove link boxes and write URLs in blue
\DeclareOption{hidelinks}{%
    \hypersetup{%
        colorlinks=true,%
        linkcolor=black,%
        citecolor=black,%
        urlcolor=blue%
    }%
}

% Add the University logo in the head of each page
\DeclareOption{headlogo}{%
    \def\@headlogo{true}%
}

% Encloses the contents of the front and back cover in a rectangular frame
\DeclareOption{framedcover}{%
    \def\@framedcover{true}%
}

\ProcessOptions\relax

\RequirePackage[utf8]{inputenc}
\RequirePackage{xurl}
\RequirePackage[table]{xcolor} % to set color for tables
\RequirePackage{tikz}
\usetikzlibrary{arrows,shapes,positioning,shadows,trees,calc}
\RequirePackage{amsmath} % codes
\RequirePackage{setspace} % space algorithm
\RequirePackage{algorithm}
\RequirePackage{algorithmicx}
\RequirePackage{algpseudocode}
\algdef{SE}[DOWHILE]{Do}{doWhile}{\algorithmicdo}[1]{\algorithmicwhile\ #1}%
\RequirePackage{subcaption} % For images
\RequirePackage{graphicx} % For grouping images
\RequirePackage[colorinlistoftodos]{todonotes}
\RequirePackage{geometry}
\geometry{
    a4paper,
    left=2.5cm,
    right=2.5cm,
    top=2.5cm,
    bottom=2.5cm,
    includefoot,
    includehead
}
\RequirePackage{amsfonts} % For mathematical expressions
\renewcommand{\baselinestretch}{1.5} % Line space
\RequirePackage{enumitem} % for enumerate
\RequirePackage[none]{hyphenat} % jumps and justifying text
\RequirePackage{float}
\RequirePackage{import}

\RequirePackage{color}

%%%%%%%%%%%%%%%%%%%%%%%%%%%%
%%%%%%%%%%%%% COLOR %%%%%%%%
\definecolor{gray}{rgb}{0.4,0.4,0.4}
\definecolor{cyan}{rgb}{0.0,0.6,0.6}
\definecolor{babyblue}{rgb}{0.54, 0.81, 0.94}
\definecolor{darkblue}{rgb}{0.0,0.0,0.6}
\definecolor{palegreen}{rgb}{0.6, 0.98, 0.6}
\definecolor{palegoldenrod}{rgb}{0.93, 0.91, 0.67}

%%%%%% HEADERS AND FOOTER %%%%%%
\RequirePackage{fancyhdr}
\RequirePackage{adjustbox}

\fancypagestyle{fancy}{
    \fancyhead[L]{\small\nouppercase{\leftmark \hfill \rightmark}}
    % Sets the corresponding right head depending on the selected option
    \ifdefined\@headlogo
        \rhead{
            \begin{picture}(0,0)
                \put(0,0){
                    \adjustbox{trim={.1\width} {.11\height} {0.1\width} {.0\height},clip}
                    {
                        \includegraphics[width=1.25cm]{pictures/logouex.pdf}
                    }
                }
            \end{picture}
        }
    \else
        \rhead{}
    \fi
}


%%% Commands for title pages and hyperref meta-data
\RequirePackage{changepage}
\RequirePackage{ragged2e}

% \clearheadinfo command resets the metadata information for the document.
% It sets default values for the author, title, type of studies, studies, and keywords.
\def\clearheadinfo{\gdef \tfeEPCC@author {Estudiante}%
                   \gdef \tfeEPCC@title {Título trabajo fin de estudios}%
                   \gdef \tfeEPCC@tipoEstudios {Grado o Máster}%
                   \gdef \tfeEPCC@estudios {Nombre de los Estudios}%
                   \gdef \tfeEPCC@keywords {Palabras clave del trabajo}%
}
\clearheadinfo

% Save the original \author command
\let\original@author\author

% Redefine the \author command to store the author name and update the PDF metadata
\renewcommand{\author}[1]{%
  % Call the original \author command
  \original@author{#1}%
  % Store the author name in a macro
  \def \tfeEPCC@author {#1}%
  % Update the PDF metadata with the author name
  \hypersetup{pdfauthor={\tfeEPCC@author}}%
}

% Save the original \title command
\let\original@title\title

% Redefine the \title command to set the document title and update the PDF metadata
\renewcommand{\title}[1]{%
  % Call the original \title command
  \original@title{#1}%
  % Store the title of the thesis in a macro
  \def \tfeEPCC@title {#1}%
  % Update the PDF metadata with the title
  \hypersetup{pdftitle={\tfeEPCC@title}}%
}

% The \keywords command sets the keywords for the document and updates the PDF metadata.
\providecommand{\keywords}[1]{%
  \begingroup%
  \def\and{{, }}%
  \xdef\tfeEPCC@keywords{#1}%
  \hypersetup{pdfkeywords={\tfeEPCC@keywords}}%
  \endgroup%
}

\providecommand{\printkeywords}{%
  {\tfeEPCC@keywords}%
}

% The \estudiante command sets the author, type of studies, and studies for the document.
% It also updates the PDF metadata with the provided information.
% Usage: \estudiante{Author Name}{Type of Studies}{Name of the Studies}
% Example: \estudiante{John Doe}{Máster}{Máster Universitario en Ingeniería Informática}
\newcommand{\estudiante}[3]{%
  \author{#1}%
  \def \tfeEPCC@tipoEstudios {#2}%
  \def \tfeEPCC@estudios {#3}%
  \hypersetup{pdfsubject={Trabajo Fin de {\tfeEPCC@tipoEstudios} de {\tfeEPCC@author} en el {\tfeEPCC@estudios} de la Escuela Politécnica de Cáceres (UEx)}}%
}

% The \portadaTFE command creates the title page for the thesis document.
% It takes one argument which is the call and year of submission of the thesis.
% Usage: \portadaTFE{Call, Year}
\newcommand{\portadaTFE}[1]{
    \begin{titlepage}
        \begin{adjustwidth}{0cm}{0cm}
            \begin{tikzpicture}[remember picture, overlay]
                \usetikzlibrary{calc}
                \ifdefined\@framedcover
                    \draw[line width = 1.5pt] ($(current page.north west) + (1in,-1in)$) rectangle ($(current page.south east) + (-1in,1in)$);
                \fi
            \end{tikzpicture}

            {
                \parskip=0pt
                \noindent
                \vspace{-3.5em}
                \vspace{-2em}

                \noindent
                \begin{minipage}[t]{0.45\textwidth}
                    \hspace{8pt}
                    \includegraphics[height=2.64cm]{pictures/logouex.pdf}
                \end{minipage}
                \hfill
                \begin{minipage}[t]{0.45\textwidth}
                    \raggedleft
                    \includegraphics[height=2.475cm]{pictures/logoepcc.pdf}
                    \hspace{8pt}
                \end{minipage}\\[1.5cm]
            }
        
        
            \begin{center}
                % Upper part of the page
                \begin{adjustwidth}{1.5cm}{1.5cm}
                    \centering
                    \textsc{\LARGE Universidad de Extremadura}\\[4cm]
            
                    \textsc{\Large Escuela Politécnica}\\[0.5cm]
                    \textsc{\Large \tfeEPCC@estudios}\\[3cm]
                    \textsc{\Large Trabajo Fin de \tfeEPCC@tipoEstudios}\\[0.5cm]
                    { \Large \bfseries \tfeEPCC@title}\\[1.0cm]
                \end{adjustwidth}
                \vfill
                % Bottom of the page
                \begin{flushright}
                    { \large \bfseries \tfeEPCC@author} \hspace*{1.25cm} \\%[0.5cm]
                    { \large \bfseries #1} \hspace*{1.25cm} \\[0.5cm]
                \end{flushright}
                \vfill
            \end{center}
        \end{adjustwidth}
    \end{titlepage}
}

\RequirePackage{pgfkeys}
\RequirePackage{xstring}

% Define keys for the \contraportadaTFE command
\pgfkeys{/contraportadaTFE/.is family, /contraportadaTFE,
  default/.style = 
  {studentGender = {}, tutor = {Tutor},
   tutorGender = {}, cotutor = {}, cotutorGender = {}},
   studentGender/.store in = \@studentGender,
   tutor/.store in = \@tutor,
   tutorGender/.store in = \@tutorGender,
   cotutor/.store in = \@cotutor,
   cotutorGender/.store in = \@cotutorGender,
}

% The \contraportadaTFE command generates the back cover page for the thesis.
% It takes a key-value argument to set the student's gender, tutor's name and gender, and optionally a co-tutor's name and gender.
% - studentGender: (Optional) Gender of the student ('m' or none for male or neutral, 'f' for female, only female option alters the layout)
% - tutor: Name of the tutor
% - tutorGender: (Optional) Gender of the tutor ('m' or none for male or neutral, 'f' for female, only female option alters the layout)
% - cotutor: (Optional) Name of the co-tutor
% - cotutorGender: (Optional) Gender of the co-tutor ('m' or none for male or neutral, 'f' for female, only female option alters the layout)
% Example: \contraportadaTFE{studentGender=m, tutor={John Doe}, tutorGender=m, cotutor={Jane Smith}, cotutorGender=f}
\newcommand{\contraportadaTFE}[1]{
    \pgfkeys{/contraportadaTFE, default, #1}
    \begin{titlepage}
        \begin{adjustwidth}{0cm}{0cm}
            \begin{tikzpicture}[remember picture, overlay]
                \usetikzlibrary{calc}
                \ifdefined\@framedcover
                    \draw[line width = 1.5pt] ($(current page.north west) + (1in,-1in)$) rectangle ($(current page.south east) + (-1in,1in)$);
                \fi
            \end{tikzpicture}

            {
                \parskip=0pt
                \noindent
                \vspace{-3.5em}
                \vspace{-2em}

                \noindent
                \begin{minipage}[t]{0.45\textwidth}
                    \hspace{8pt}
                    \includegraphics[height=2.64cm]{pictures/logouex.pdf}
                \end{minipage}
                \hfill
                \begin{minipage}[t]{0.45\textwidth}
                    \raggedleft
                    \includegraphics[height=2.475cm]{pictures/logoepcc.pdf}
                    \hspace{8pt}
                \end{minipage}\\[1.5cm]
            }
        
            \begin{center}
                % Upper part of the page
                \begin{adjustwidth}{1.5cm}{1.5cm}
                    \centering
                    \textsc{\LARGE Universidad de Extremadura}\\[3cm]
            
                    \textsc{\Large Escuela Politécnica}\\[0.5cm]
                    \textsc{\Large \tfeEPCC@estudios}\\[2.5cm]
                    \textsc{\Large Trabajo Fin de \tfeEPCC@tipoEstudios}\\[0.5cm]
                    { \Large \bfseries \tfeEPCC@title}
                \end{adjustwidth}\vfill  
                % Bottom of the page
                { \large \bfseries Autor\IfStrEq{\@studentGender}{f}{a}{}: \tfeEPCC@author}\\[0.5cm]
                { \large \bfseries Tutor\IfStrEq{\@tutorGender}{f}{a}{}: \@tutor}\\[0.5cm]
                \IfStrEq{\@cotutor}{}{}{
                    { \large \bfseries Co-Tutor\IfStrEq{\@cotutorGender}{f}{a}{}: \@cotutor}\\[0.5cm]
                }
            \end{center}
        \end{adjustwidth}
    \end{titlepage}
}

% Set language-specific names for various document parts
\AtBeginDocument{%
    \makeatletter%
    \@ifpackagewith{babel}{spanish}%
    {%
         % Spanish translations
        \addto\captionsspanish{%
            \renewcommand\appendixname{Anexo}%
        }%
        \renewcommand{\appendixtocname}{Anexos}%
        \renewcommand{\appendixpagename}{Anexos}%
        \renewcommand{\chapterautorefname}{Capítulo}%
        \renewcommand{\sectionautorefname}{Sección}%
        \renewcommand{\subsectionautorefname}{Subsección}%
        \renewcommand{\figureautorefname}{Figura}%
        \renewcommand{\equationautorefname}{Ecuación}%
        \renewcommand{\tableautorefname}{Tabla}%
        \renewcommand{\appendixautorefname}{Anexo}%
        \renewcommand{\mtctitle}{Contenidos}%
        \def\introductionname{Introducción}%
        \def\objectivesname{Objetivos}%
        \def\stateoftheartname{Estado del Arte}%
        \def\methodologyname{Metodología}%
        \def\implementationdevelopmentname{Implementación y desarrollo}%
        \def\resultsname{Resultados}%
        \def\conclusionsname{Conclusiones y trabajos futuros}%
        \def\bibliographyname{Bibliografía}%
    }%
    {%
        % English translations
        \renewcommand{\chapterautorefname}{Chapter}%
        \renewcommand{\sectionautorefname}{Section}%
        \renewcommand{\subsectionautorefname}{Subsection}%
        \def\introductionname{Introduction}%
        \def\objectivesname{Objectives}%
        \def\stateoftheartname{State of the Art}%
        \def\methodologyname{Methodology}%
        \def\implementationdevelopmentname{Implementation and development}%
        \def\resultsname{Results}%
        \def\conclusionsname{Conclusions and future works}%
        \def\bibliographyname{Bibliography}%
    }%
    \makeatother%
}

% The minted package is used for syntax highlighting of source code.
% It provides a flexible and customizable way to include code with syntax highlighting in LaTeX documents.
\RequirePackage{minted}
\usemintedstyle{perldoc}
% Set options for the minted package
\setminted{
    frame=lines,            % Add a frame around the code
    framesep=2mm,           % Set the space between the frame and the code
    autogobble=true,        % Automatically remove common leading whitespace
    fontsize=\small,        % Set the font size for the code
    linenos,                % Show line numbers
    numbersep=10pt,         % Set the space between the line numbers and the code
    breaklines=true,        % Allow breaking long lines
    breakanywhere=true      % Allow breaking at any character
}

\renewcommand{\theFancyVerbLine}{\sffamily\footnotesize\textcolor{black}{\arabic{FancyVerbLine}}}

\BeforeBeginEnvironment{minted}{\begingroup \hyphenpenalty=50 \exhyphenpenalty=50 \relax}
\AfterEndEnvironment{minted}{\endgroup}

\NewCommandCopy{\originalinputminted}{\inputminted}
\renewcommand{\inputminted}[3][]{
    \begingroup
        \hyphenpenalty=50 \exhyphenpenalty=50
        \originalinputminted[#1]{#2}{#3}
    \endgroup
}

% Command for starting the appendices
\providecommand{\startappendices}{
    \cleardoublepage
    \begingroup
        \let\ps@plain\ps@empty
        \appendix
        \addappheadtotoc
        \clearpage
        \appendixpage
    \endgroup
}

% Command for printing the bibliography
% It takes the style of the bibliography as a parameter, using 'unsrturl' if not specified or empty
\providecommand{\makebibliography}[1][unsrturl]{
    \phantomsection
    \begingroup
        \let\ps@plain\ps@empty
        \addcontentsline{toc}{chapter}{\bibliographyname}
        \IfStrEq{#1}{}{
            \bibliographystyle{unsrturl}
        }
        {
            \bibliographystyle{#1}
        }
        \bibliography{LocalBibliography.bib}
        \clearpage
    \endgroup
}